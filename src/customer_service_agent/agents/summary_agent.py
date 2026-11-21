from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from customer_service_agent.agents.llm_utils import get_llm, structured_llm_call
from customer_service_agent.agents.schemas import SummaryResponse
from customer_service_agent.pipeline.state import ChatState

SUMMARY_SYSTEM_PROMPT = """你是一个专业、温暖、高情商的电商智能客服。
直接输出给用户的回复文本，不要输出JSON、不要markdown、不要```包裹、不要额外说明。

【重要要求】
1. 语气要亲切，带上称呼（如：亲爱的顾客您好），绝不与用户争吵。
2. 如果【背景资料】中有订单结果，清晰告知用户。
3. 如果【背景资料】中有知识库助手生成的回答，请直接引用或润色，准确解答。
4. 如果【背景资料】中生成了工单，请安抚用户情绪，并告知已转人工（给出工单号）。
5. 回复长度控制在 250 字以内。"""


class SummaryAgent:
    def __init__(self):
        self.llm = get_llm()

    async def __call__(self, state: ChatState) -> dict:
        print("-> [Summary Agent] 正在生成最终回复...")
        context_parts = []
        if state.get("tool_results"):
            context_parts.append(f"【工具查询结果】: {state['tool_results']}")
        if state.get("knowledge_answer"):
            context_parts.append(f"【知识库助手生成的回答】: {state['knowledge_answer']}")
        if state.get("escalation_ticket"):
            context_parts.append(f"【已转人工工单】: {state['escalation_ticket']}")
        context = "\n".join(context_parts) if context_parts else "暂无额外背景资料。"

        prompt = f"""用户当前提问: {state['user_message']}
    【背景资料】
    {context}

    你是一个专业、温暖、高情商的电商智能客服。
    语气亲切，带上称呼，250字以内，直接输出回答，不要JSON，不要markdown。
    """
        messages = [SystemMessage(content=SUMMARY_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        # 这里不再用structured_llm_call，直接astream
        full_content = ""
        async for chunk in self.llm.astream(messages, config={"tags": ["summary_stream"]}):
            full_content += chunk.content
        print(f"   ✅ 最终回复已生成")
        return {
            "final_response": full_content,
            "messages": [AIMessage(content=full_content)],
            "thought_chain": state.get("thought_chain", []) + [{"agent": "summary", "output": "已生成最终回复"}]
        }
