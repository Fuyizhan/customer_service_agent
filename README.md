# 🛎️ 电商智能客服 Agent

基于 **LangGraph 多智能体状态机** 的电商客服系统：意图识别 → 工具调用 / RAG 知识库 / 工单转人工 → 统一话术汇总，支持**复合意图逐项处理**、**真实向量检索**、**全链路 SSE 流式输出**。

## 💡 解决什么问题

单 Agent 挂载全部工具的做法，在真实客服场景会遇到三个硬伤：

1. **复合意图被丢弃** —— 用户说"查我的订单，顺便问下能退货吗"，单标签分类只能选一个，另一个诉求直接消失。
2. **RAG 名不副实** —— 很多同类项目用关键词匹配冒充向量检索，且没有相关性阈值，用户问"今天天气"也能"查"到售后政策并一本正经地回答。
3. **LLM 输出裸解析** —— `json.loads()` 直接解析模型返回，格式一乱整个服务 500。

本项目用 **Router-Worker 架构 + 循环路由 + 真实 pgvector 检索 + Pydantic 强约束** 逐一解决。

## 🏗️ 架构

```text
                    ┌─────────────┐
              ┌────▶│   Router    │◀────┐  复合意图回环
              │     │ 意图识别+派发 │     │
              │     └──────┬──────┘     │
              │            │            │
        ┌─────┴────┬───────┴──────┬─────┴─────┐
        ▼          ▼              ▼           ▼
   ┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐
   │  Tool  │ │Knowledge │ │Escalation│ │Summary │
   │查订单/物流│ │ pgvector │ │  生成工单  │ │最终话术 │
   └───┬────┘ └────┬─────┘ └────┬─────┘ └───┬────┘
       │           │            │            │
       └───────────┴────────────┴────────────┘
                        │
                     ┌──▼──┐
                     │ END │
                     └─────┘
```

**执行链路：**

1. `Router` 分析用户话术，输出意图列表（按重要性降序），取第一个作为主意图，其余存入 `pending_intents`
2. 条件边按主意图派发到 `Tool` / `Knowledge` / `Escalation`
3. 分支执行完**回环到 `Router`**，若 `pending_intents` 非空则继续派发下一个意图
4. 队列清空后进入 `Summary`，汇总本轮所有结果，统一生成客服话术
5. `Summary` 结束 → `END`

**防死循环：** `loop_count` 超过 5 次强制中止并进入 `Summary`。

## 🛠️ 技术栈

| 层 | 选型 |
|----|------|
| 后端框架 | FastAPI + Pydantic v2 |
| Agent 编排 | LangGraph（StateGraph + 条件边 + 循环 + Checkpointer） |
| LLM | DeepSeek（OpenAI 兼容协议），`tenacity` 指数退避重试 |
| Embedding | 阿里云百炼 `text-embedding-v3`（1024 维） |
| 数据库 | PostgreSQL 16 + pgvector，SQLAlchemy 2.0 Async |
| 前端 | Next.js 16（App Router + TS）+ Tailwind CSS |
| 依赖管理 | uv（`pyproject.toml` + `uv.lock`） |
| 部署 | Docker Compose（uv 多阶段构建 + Next standalone） |

## ✨ 核心工程亮点

### 1. 循环路由解决复合意图

传统并行扇出（Parallel Branching）在意图数超过 2 时，图结构会指数级复杂。本项目改用**串行回环**：

- `Router` 既做意图识别，也做任务派发
- 每轮只执行一个意图，执行完回到 `Router` 取下一个
- 上下文天然收敛（上一轮的工具结果留在 state 里，下一轮可复用）
- 熔断可控（一个 `loop_count` 就能兜住所有死循环场景）

### 2. 真实 RAG + 相关性阈值兜底

```python
# rag_service.py 核心逻辑
stmt = (
    select(
        KnowledgeDoc.content,
        KnowledgeDoc.embedding.cosine_distance(query_vector).label("distance"),
    )
    .order_by("distance")
    .limit(limit)
)
rows = result.all()
filtered = [row.content for row in rows if row.distance < threshold]  # 默认 0.5
```

**没有阈值的 RAG 等于没有 RAG。** 检索结果全部超过阈值时直接丢弃，`KnowledgeAgent` 返回"未查询到相关政策，建议转人工"，从架构上杜绝"问天气也能查到售后政策"。

### 3. 三层结构化输出防护

| 层 | 手段 |
|----|------|
| 模型侧 | `with_structured_output(schema, method="json_mode")` 约束输出格式 |
| 校验侧 | Pydantic Schema 强类型校验（`Literal` 限定枚举值） |
| 容错侧 | `tenacity` 指数退避重试 3 次；工单生成失败走固定模板兜底 |

所有中间节点（Router / Knowledge / Escalation）全部走这套链路，告别 `json.loads` 裸解析。

### 4. 精确的全链路流式

用 `astream_events` 做旁路监听，但**流事件是全模型调用共享的**——Router 的结构化输出也会触发 `on_chat_model_stream`，导致前端收到 `{"intents":[...]}` 这类 JSON 噪音。而且 `metadata.langgraph_node` 在流事件上常常是 `None`，不能用来过滤。

**解决方案：给 Summary 的 `astream` 打自定义 tag，SSE 层只认带该 tag 的事件。**

```python
# SummaryAgent
async for chunk in self.llm.astream(messages, config={"tags": ["summary_stream"]}):
    full_content += chunk.content

# SSE 层
elif kind == "on_chat_model_stream":
    if "summary_stream" in (event.get("tags") or []):
        yield sse({"type": "token", "content": event["data"]["chunk"].content})
```

前端配合实现：`TextDecoder(stream: true)` 处理中文跨块截断、`buffer` 处理 SSE 半包、`AbortController` 处理并发竞态、`seq` 兜底去重。

### 5. 会话记忆与历史回填

`MemorySaver` 按 `thread_id` 存状态快照，前端 `sessionStorage` 持久化 `thread_id`。配套 `GET /api/chat/history` 从 checkpointer 读取快照回填，解决"刷新页面历史丢失"。

## 📂 项目结构

```text
customer_service_agent/
├── src/customer_service_agent/
│   ├── agents/                      # 多 Agent 业务层
│   │   ├── router_agent.py          # 意图识别 + 任务派发
│   │   ├── tool_agent.py            # 订单/物流工具调用
│   │   ├── knowledge_agent.py       # RAG 知识库问答
│   │   ├── escalation_agent.py      # 投诉工单生成
│   │   ├── summary_agent.py         # 最终话术汇总（流式输出）
│   │   ├── tools.py                 # @tool 装饰的 Function Calling 工具
│   │   ├── rag_service.py           # pgvector 向量检索（带阈值）
│   │   ├── llm_utils.py             # LLM 封装 + 重试 + 结构化调用
│   │   └── schemas.py               # LLM 输出契约（Pydantic）
│   ├── pipeline/
│   │   ├── state.py                 # ChatState 定义
│   │   └── graph.py                 # LangGraph 编排 + 条件边 + 熔断
│   ├── api/
│   │   ├── main.py                  # FastAPI 入口 + SSE 流式接口
│   │   └── schemas.py               # HTTP 请求/响应契约
│   ├── db/
│   │   ├── models.py                # orders / shipments / knowledge_docs
│   │   ├── session.py               # 异步引擎 + 建表 + pgvector 扩展
│   │   ├── seed_data.py             # 订单/物流种子数据
│   │   └── ingest_knowledge.py      # 知识库真实向量入库脚本
│   └── config.py                    # pydantic-settings 配置
├── customer_service_frontend/       # Next.js 16 前端
│   └── src/app/
│       ├── page.tsx                 # 聊天界面（SSE 流式渲染）
│       └── api/chat/
│           ├── stream/route.ts      # SSE 转发
│           └── history/route.ts     # 历史消息查询
├── Dockerfile                       # 后端镜像（uv 多阶段构建）
├── docker-compose.yml               # DB + 后端 + 前端
├── pyproject.toml / uv.lock
└── .env.example
```

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

```bash
git clone <your-repo-url>
cd customer_service_agent
cp .env.example .env   # 填入 LLM_API_KEY 和 EMBEDDING_API_KEY
docker compose up -d --build

# 首次启动后，导入知识库真实向量
docker compose exec backend python -m src.customer_service_agent.db.ingest_knowledge
```

- 前端：<http://localhost:3000>
- 后端 API 文档：<http://localhost:8000/docs>

### 方式二：本地开发

**后端：**

```bash
uv sync
uv run fastapi dev src/customer_service_agent/api/main.py
```

**知识库入库（首次必做）：**

```bash
uv run python -m customer_service_agent.db.ingest_knowledge
```

**前端：**

```bash
cd customer_service_frontend
npm install
npm run dev
```

### 环境变量

```env
# 大模型（对话）
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# Embedding（阿里云百炼）
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
```

> ⚠️ DeepSeek 官方不提供 Embedding 模型，需单独接入百炼 / 硅基流动等兼容 OpenAI 协议的服务。`KnowledgeDoc.embedding` 的维度（当前 `Vector(1024)`）必须与所选 Embedding 模型输出维度一致。

## 🔌 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 同步接口，返回完整回复（Swagger 调试用） |
| POST | `/api/chat/stream` | SSE 流式接口 |
| GET | `/api/chat/history?thread_id=xxx` | 查询会话历史消息 |

### SSE 事件格式

```text
data: {"type": "status", "content": "正在执行: router..."}
data: {"type": "status", "content": "正在执行: tool..."}
data: {"type": "status", "content": "正在执行: router..."}
data: {"type": "status", "content": "正在执行: summary..."}
data: {"type": "token", "content": "亲"}
data: {"type": "token", "content": "爱的"}
...
data: {"type": "done"}
```

| `type` | 含义 |
|--------|------|
| `status` | 节点执行状态（用于前端展示"正在执行 xx"） |
| `token` | Summary 节点的流式 token |
| `done` | 流结束 |
| `error` | 异常信息 |

## ⚠️ 已知限制

- **Checkpointer 为 `MemorySaver`**：状态存在后端进程内存中。前端刷新不影响（进程未重启），但**后端重启即丢失**。生产环境应替换为 `PostgresSaver`，以支持多副本部署与服务重启恢复。
- **知识库入库为离线脚本**：`ingest_knowledge.py` 单独执行，不走服务启动流程。生产环境应改为后台任务 + 增量更新。

## 📄 License

MIT