# src/customer_service_agent/agents/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, List

# 1. 路由意图的强约束
class RouterOutput(BaseModel):
    # 改成列表，允许大模型返回多个意图
    intents: List[Literal["order_query", "product_inquiry", "complaint", "general"]] = Field(
        description="用户的意图列表。如果用户一句话里有多个需求（比如既问产品又要查订单），请把相关意图都提取出来。"
    )
    reason: str = Field(description="分类的简短理由")

# 2. 工单的强约束
class TicketSchema(BaseModel):
    summary: str = Field(description="问题简述，20字以内")
    category: str = Field(description="问题类别")
    urgency: Literal["high", "medium", "low"] = Field(description="紧急程度")
    suggested_action: str = Field(description="建议处理方法")

class KnowledgeResponse(BaseModel):
    answer: str = Field(description="基于参考资料生成的客服回答，不要包含任何多余的解释")

class SummaryResponse(BaseModel):
    final_reply: str = Field(description="最终发给用户的客服回复话术，要亲切专业，控制在250字以内")