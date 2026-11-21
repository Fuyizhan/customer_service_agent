# src/customer_service_agent/pipeline/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from customer_service_agent.pipeline.state import ChatState
from customer_service_agent.agents.router_agent import RouterAgent
from customer_service_agent.agents.tool_agent import ToolAgent
from customer_service_agent.agents.knowledge_agent import KnowledgeAgent
from customer_service_agent.agents.escalation_agent import EscalationAgent
from customer_service_agent.agents.summary_agent import SummaryAgent

def route_decision(state: ChatState):
    """条件路由逻辑"""
    primary = state.get("primary_intent", "general")
    if primary == "order_query":
        return "tool"
    elif primary == "complaint":
        return "escalation"
    elif primary == "general":
        return "summary"
    elif primary == "summary":
        return "summary"
    else:
        return "knowledge"

def build_graph():
    builder = StateGraph(ChatState)
    
    # 实例化所有 Agent
    router = RouterAgent()
    tool = ToolAgent()
    knowledge = KnowledgeAgent()
    escalation = EscalationAgent()
    summary = SummaryAgent()

    # 添加节点
    builder.add_node("router", router)
    builder.add_node("tool", tool)
    builder.add_node("knowledge", knowledge)
    builder.add_node("escalation", escalation)
    builder.add_node("summary", summary)

    # 入口指向 Router
    builder.set_entry_point("router")

    # 条件路由分发
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "tool": "tool",
            "knowledge": "knowledge",
            "escalation": "escalation",
             "summary": "summary"
        }
    )

    # 【核心改造】分支执行完后，全部指回 router！形成循环！
    builder.add_edge("tool", "router")
    builder.add_edge("knowledge", "router")
    builder.add_edge("escalation", "router")

    # Summary 结束后退出
    builder.add_edge("summary", END)

    # 编译图并加上记忆体
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)

# 导出全局图实例
agent_graph = build_graph()