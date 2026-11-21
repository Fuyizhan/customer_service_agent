# src/customer_service_agent/pipeline/state.py
from typing import TypedDict, List, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class ChatState(TypedDict):
    # 核心对话历史（add_messages 会自动把新消息 append 进去）
    messages: Annotated[List[BaseMessage], add_messages]
    user_message: str
    # 意图路由
    intents: Optional[List[str]] 
    primary_intent: Optional[str]      # 本次执行的主意图
    pending_intents: Optional[List[str]]
    loop_count: Optional[int]  # <--- 新增：记录循环次数，防止死循环
    # 分支数据
    retrieved_docs: List[dict]
    tool_results: List[dict]
    knowledge_answer: Optional[str]
    # 转人工工单
    escalation_ticket: Optional[dict]
    # 最终回复
    final_response: Optional[str]
    # 思考链路（给前端展示用）
    thought_chain: List[dict]