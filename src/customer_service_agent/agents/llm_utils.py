# src/customer_service_agent/agents/llm_utils.py
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from typing import Any, List
from langchain_core.messages import BaseMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from customer_service_agent.config import settings  # 假设你写了 config 读取 .env
import openai
import asyncio

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=0.1,
        timeout=60.0
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, asyncio.TimeoutError)),
    reraise=True
)
async def _call_llm_with_retry(structured_llm, messages):
    return await structured_llm.ainvoke(messages)

async def structured_llm_call(llm: ChatOpenAI, messages: List[BaseMessage], schema: type[BaseModel]) -> Any:
    structured_llm = llm.with_structured_output(schema, method="json_mode")
    return await _call_llm_with_retry(structured_llm, messages)