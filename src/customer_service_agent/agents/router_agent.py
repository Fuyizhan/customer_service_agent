# src/customer_service_agent/agents/router_agent.py
from langchain_core.messages import HumanMessage, SystemMessage
from customer_service_agent.pipeline.state import ChatState
from customer_service_agent.agents.llm_utils import get_llm, structured_llm_call
from customer_service_agent.agents.schemas import RouterOutput

ROUTER_SYSTEM_PROMPT = """你是一个专业的电商智能客服意图识别专家。你的任务是分析用户的话，并提取出所有的意图。

【输出格式】
只能输出合法的 JSON 对象，不要包含任何 Markdown 标记，包含下面两个字段：
- intents: list[str]，可选值：order_query、complaint、product_inquiry、general
- reason: str，简短说明判断理由
示例：{"intents":["product_inquiry","order_query"], "reason":"用户说手机坏了要退货，同时查询另一单物流"}

【可用意图定义】
- order_query: 用户想要查询订单状态、物流进度、发货时间等。
- product_inquiry: 用户询问商品的功能、规格、价格、库存或退换货/保修政策。
- complaint: 用户表达强烈不满、要求退款、投诉质量问题或要求转人工。
- general: 问候、闲聊、感谢，或者完全无法归类的其他问题。

【重要要求】
1. 用户的一句话中可能包含多个意图（例如：“我的手机坏了要退货，顺便查下另一单到哪了”），请把你识别到的意图都提取出来。
2. 请按意图的强烈程度或重要性进行**降序排列**，把最主要的意图放在第一个。优先级顺序为：complaint > order_query > product_inquiry > general。
3. 如果用户情绪激动，必须把 complaint 放在第一位。
"""

class RouterAgent:
    def __init__(self):
        self.llm = get_llm()

    async def __call__(self, state: ChatState) -> dict:

        # 获取当前的循环次数，如果是第一轮则是 0
        loop_count = state.get("loop_count", 0)
        
        # 【第一道防线】熔断机制
        if loop_count >= 5:
            print("⚠️ [Router] 循环次数达到上限(5次)，强制终止并进入 Summary。")
            return {
                "primary_intent": "summary",
                "loop_count": loop_count,
                "thought_chain": state.get("thought_chain", []) + [{"agent": "router", "output": "循环超限，强制汇总"}]
            }
        
        # 1. 检查是不是第一轮（如果是第一轮，才做意图识别）
        if not state.get("intents"):
            print("-> [Router] 首次分析意图...")
            messages = [
                SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=f"请判断以下用户话术的意图：{state['user_message']}")
            ]
            result = await structured_llm_call(self.llm, messages, RouterOutput)
            
            intents = result.intents or ["general"]
            # 初始化待办清单
            pending = intents[1:] if len(intents) > 1 else []
            primary = intents[0]

            print(f"   识别到意图队列: {intents}")
            return {
                "intents": intents,
                "primary_intent": primary,
                "pending_intents": pending,
                "loop_count": loop_count + 1, # 【修复2】增加计数器
                "thought_chain": state.get("thought_chain", []) + [{"agent": "router", "output": f"识别意图: {intents}"}]
            }
        
        # 2. 如果不是第一轮（说明是分支执行完绕回来的）
        # 从待办清单里取下一个
        pending = state.get("pending_intents", [])
        if pending:
            next_intent = pending[0]
            remaining = pending[1:]
            print(f"-> [Router] 发现还有待办意图: {next_intent}，继续执行...")
            return {
                "primary_intent": next_intent,
                "pending_intents": remaining,
                "loop_count": loop_count + 1, # 【修复2】增加计数器
                "thought_chain": state.get("thought_chain", []) + [{"agent": "router", "output": f"继续执行意图: {next_intent}"}]
            }
        
        # 3. 如果没有待办了，走向汇总
        print("-> [Router] 所有意图处理完毕，准备汇总...")
        return {
            "primary_intent": "summary",
            "loop_count": loop_count
        }

