from langchain_core.messages import SystemMessage, HumanMessage
from customer_service_agent.agents.llm_utils import get_llm
from customer_service_agent.pipeline.state import ChatState
from customer_service_agent.agents.llm_utils import get_llm, structured_llm_call
from customer_service_agent.agents.schemas import KnowledgeResponse
from customer_service_agent.agents.rag_service import rag_service

KNOWLEDGE_SYSTEM_PROMPT = """你是一个严谨的电商知识库问答专家。你的任务是根据【参考资料】回答用户的问题。

【重要要求】
1. 必须完全基于【参考资料】中的内容进行回答，绝对不允许编造参考资料中没有的信息。
2. 如果【参考资料】为空，或者资料不足以回答问题，请务必输出这句标准话术：“抱歉，我暂时没有查询到相关政策，建议您转接人工客服处理。”
3. 回答要简洁专业，控制在 200 字以内。
【输出格式】
只返回JSON，有且仅有一个字段 answer，不要额外文字、不要markdown、不要```包裹。
示例：{"answer":"这里是回答内容"}"""

class KnowledgeAgent:
    def __init__(self):
        self.llm = get_llm()

    async def __call__(self, state: ChatState) -> dict:
        print("-> [Knowledge Agent] 正在检索知识库...")
        
        # 1. 模拟检索
        user_query = state["user_message"]
        # 调用向量检索函数
        retrieved_docs = await rag_service.query_similar_docs(query=user_query, limit=3)
        
        # 2. 组装消息
        context = "\n".join(retrieved_docs)
        messages = [SystemMessage(content=KNOWLEDGE_SYSTEM_PROMPT)]
        history_messages = state.get("messages", [])
        messages.extend(history_messages[-10:])

        messages.append(HumanMessage(content=f"用户问题：{state['user_message']}\n\n【参考资料】\n{context}"))

        # 3. 使用带重试和强校验的结构化调用
        result = await structured_llm_call(self.llm, messages, KnowledgeResponse)
        
        # 这里 result 是 KnowledgeResponse 对象，使用 .answer 获取文本
        print(f"   ✅ 知识库回答生成完毕")
        
        return {
            "retrieved_docs": retrieved_docs,
            "knowledge_answer": result.answer, 
            "thought_chain": state.get("thought_chain", []) + [{"agent": "knowledge", "output": "已生成知识库解答"}]
        }