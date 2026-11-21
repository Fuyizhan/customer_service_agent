# src/customer_service_agent/api/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入的对话内容")
    thread_id: str = Field(..., description="会话ID，用于多轮对话记忆")

class ThoughtStep(BaseModel):
    agent: str
    output: str

class ChatResponse(BaseModel):
    reply: str = Field(..., description="最终回复给用户的文本")
    intent: Optional[str] = Field(None, description="识别出的主意图")
    thought_chain: List[ThoughtStep] = Field(default_factory=list, description="Agent的思考链路")