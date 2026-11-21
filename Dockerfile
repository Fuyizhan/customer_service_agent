# Dockerfile.backend
FROM python:3.11-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 先只拷依赖描述文件，利用缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple


# 再拷源码
COPY . .
RUN uv sync  --no-dev

# ---------- 运行阶段 ----------
FROM python:3.11-slim

WORKDIR /app

# 只拷虚拟环境，不带 uv 和构建垃圾
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "customer_service_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]