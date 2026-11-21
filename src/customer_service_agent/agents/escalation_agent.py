# src/customer_service_agent/agents/escalation_agent.py
from langchain_core.messages import SystemMessage, HumanMessage
from customer_service_agent.agents.llm_utils import get_llm, structured_llm_call
from customer_service_agent.agents.schemas import TicketSchema
from customer_service_agent.pipeline.state import ChatState
from datetime import datetime

# 极其严谨的工单生成 Prompt
ESCALATION_SYSTEM_PROMPT = """你是一个专业的电商客诉处理专员。用户遇到了问题并需要转接人工客服。
请结合【历史对话】和【用户当前投诉内容】，生成一个结构化的内部工单，方便人工客服快速了解情况并接手。

【工单字段要求】
1. summary: 精炼总结用户的核心诉求（20字以内）。
2. category: 问题类别（只能从以下选择：物流延迟、商品质量、退款纠纷、服务态度、其他）。
3. urgency: 紧急程度（high/medium/low）。涉及资金安全、严重质量问题、辱骂冲突或威胁投诉监管部门的，必须为 high。
4. suggested_action: 给人工客服的建议处理方案（一句话说明）。

【输出格式】
只返回JSON，包含上面4个字段，不要额外文字、不要markdown、不要```包裹。
示例：
{"summary":"收到商品破损，要求退货退款","category":"商品质量","urgency":"high","suggested_action":"联系用户核实照片，优先安排退款"}
"""

class EscalationAgent:
    def __init__(self):
        self.llm = get_llm()

    async def __call__(self, state: ChatState) -> dict:
        print("-> [Escalation Agent] 正在生成人工工单...")
        
        # 1. 先将 SystemPrompt 放进去
        messages = [SystemMessage(content=ESCALATION_SYSTEM_PROMPT)]
        
        # 2. 【核心修复】拼装历史对话记录（最多取最近 10 条）
        history_messages = state.get("messages", [])
        messages.extend(history_messages[-10:])
        
        # 3. 最后加上当前用户的投诉内容
        messages.append(HumanMessage(content=f"用户当前投诉：{state['user_message']}"))
        
        try:
            # 强类型结构化调用（自带重试、校验）
            result = await structured_llm_call(self.llm, messages, TicketSchema)
            ticket = result.model_dump()
            
            # 动态生成一个工单号（格式：TK-年月日时分秒）
            ticket_id = f"TK-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            ticket["ticket_id"] = ticket_id
            
            print(f"   ✅ 已生成工单 {ticket_id}: {ticket['summary']} (紧急度: {ticket['urgency']})")
            
            return {
                "escalation_ticket": ticket,
                "thought_chain": state.get("thought_chain", []) + [
                    {"agent": "escalation", "output": f"生成工单: {ticket_id}"}
                ]
            }
            
        except Exception as e:
            # 降级兜底：如果大模型死活生成不出结构化的工单，我们直接用手写逻辑兜底
            print(f"   ⚠️ [降级触发] 工单生成失败，使用兜底工单: {e}")
            
            fallback_ticket = {
                "ticket_id": f"TK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "summary": "用户投诉/需人工介入",
                "category": "其他",
                "urgency": "medium",
                "suggested_action": "请人工客服尽快联系用户了解情况"
            }
            
            return {
                "escalation_ticket": fallback_ticket,
                "thought_chain": state.get("thought_chain", []) + [
                    {"agent": "escalation", "output": "工单生成降级，已生成兜底工单"}
                ]
            }