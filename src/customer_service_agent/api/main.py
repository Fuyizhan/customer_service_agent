# src/customer_service_agent/api/main.py
import json
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage, AIMessage
from customer_service_agent.api.schemas import ChatRequest, ChatResponse
from customer_service_agent.pipeline.graph import agent_graph
from customer_service_agent.config import settings
from customer_service_agent.db import session
from customer_service_agent.db.session import init_db_engine, create_tables_and_extension
from customer_service_agent.db.seed_data import seed_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_engine(settings.DATABASE_URL)
    await create_tables_and_extension()
    await seed_db()
    yield
    if session.engine:
        await session.engine.dispose()


app = FastAPI(lifespan=lifespan, title="智能客服Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(data: dict) -> str:
    """统一 SSE 序列化，保留中文"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_initial_state(message: str) -> dict:
    """两个接口共用，避免字段漂移"""
    return {
        "messages": [HumanMessage(content=message)],
        "user_message": message,
        "intents": [],
        "primary_intent": None,
        "pending_intents": [],
        "loop_count": 0,
        "retrieved_docs": [],
        "tool_results": [],
        "knowledge_answer": None,
        "escalation_ticket": None,
        "final_response": None,
        "thought_chain": [],
    }

'''
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await agent_graph.ainvoke(build_initial_state(req.message), config=config)
    return ChatResponse(
        reply=result.get("final_response", ""),
        intent=result.get("primary_intent") or "",
        thought_chain=result.get("thought_chain", []),
    )

'''


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_generator():
        seen_event_ids = set()   # 记录已经处理过的 LLM 调用链
        try:
            async for event in agent_graph.astream_events(
                build_initial_state(req.message), config=config, version="v2"
            ):
                kind = event["event"]
                node = (event.get("metadata") or {}).get("langgraph_node")

                # 节点开始：用 event["name"]（节点注册名）判断最准
                if kind == "on_chain_start" and event.get("name") in (
                    "router", "tool", "knowledge", "escalation", "summary"
                ):
                    yield sse({"type": "status", "content": f'正在执行: {event["name"]}...'})

                # 模型吐字：用 metadata.langgraph_node 判断（此时 name 是模型名）
                elif kind == "on_chat_model_stream" :
                    tags = event.get("tags") or []
                    if "summary_stream" in tags:
                        content = event["data"]["chunk"].content
                        if content:
                            yield sse({"type": "token", "content": content})

            yield sse({"type": "done"})

        except asyncio.CancelledError:
            # 客户端主动断开，正常退出
            raise
        except Exception as e:
            yield sse({"type": "error", "content": str(e)})
            yield sse({"type": "done"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/chat/history")
async def get_history(thread_id: str):
    """读取某个会话的历史消息"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = await agent_graph.aget_state(config)
    except Exception:
        return {"messages": []}

    if not snapshot or not snapshot.values:
        return {"messages": []}

    raw_messages = snapshot.values.get("messages", [])
    result = []
    for msg in raw_messages:
        # 只返回用户和 AI 的对话，忽略 ToolMessage 等内部消息
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})

    return {"messages": result}