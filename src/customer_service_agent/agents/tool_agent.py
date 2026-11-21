from langchain_core.messages import SystemMessage, HumanMessage
from customer_service_agent.agents.llm_utils import get_llm
from customer_service_agent.agents.tools import query_order_status, query_shipment_info
from customer_service_agent.pipeline.state import ChatState

TOOL_SYSTEM_PROMPT = """你是一个电商订单查询助手。请根据用户的提问，提取正确的参数并调用工具。
【重要要求】
1. 如果用户没有提供订单号（如 ORD-001），请先查看【历史对话】中是否提到过订单号。如果历史对话中也没有，请绝对不要瞎猜，直接告知用户需要提供订单号。
2. 如果用户提供了订单号（或通过历史对话找到了），必须原样提取，不要修改大小写或符号。
3. 只允许调用给出的工具，禁止编造不存在的工具、编造参数。
4. 参数严格按照工具定义传递，订单号必须完整原样传入，不要截断、改写。
5. 不需要输出JSON，依靠Function Calling格式返回工具调用，不要自己生成回答文本。
"""

class ToolAgent:
    def __init__(self):
        self.llm = get_llm()
        self.tools = [query_order_status, query_shipment_info]
        # 绑定工具，让大模型具备原生 Function Calling 能力
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    async def __call__(self, state: ChatState) -> dict:
        print("-> [Tool Agent] 正在提取订单参数...")
        # 1. 先把 SystemPrompt 放进去
        messages = [SystemMessage(content=TOOL_SYSTEM_PROMPT)]

        # 2. 【核心修复】拼装历史对话记录（最多取最近 10 条）
        # 这样大模型就能看到“用户上一句说的是订单 ORD-001”
        history_messages = state.get("messages", [])
        messages.extend(history_messages[-10:])

        # 3. 最后加上当前用户的话
        messages.append(HumanMessage(content=state["user_message"]))
        
        # 大模型决定是否调用工具
        response = await self.llm_with_tools.ainvoke(messages)

        if not response.tool_calls:
            print("   ⚠️ 大模型未识别出订单号")
            return {
                "tool_results": ["未能在对话中识别出有效的订单号，请提示用户提供订单号。"],
                "thought_chain": state.get("thought_chain", []) + [{"agent": "tool", "output": "未命中工具"}]
            }
            
        # 执行工具并收集结果
        results = []
        for tool_call in response.tool_calls:
            func = next((t for t in self.tools if t.name == tool_call["name"]), None)
            if func:
                res = await func.ainvoke(tool_call["args"])
                results.append(res)
                
        print(f"   ✅ 工具执行结果: {results}")
        return {
            "tool_results": results,
            "thought_chain": state.get("thought_chain", []) + [{"agent": "tool", "output": str(results)}]
        }