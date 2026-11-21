import { NextRequest } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    // 确认你的FastAPI地址：http://127.0.0.1:8000
    const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    const backendRes = await fetch(`${BACKEND}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!backendRes.ok) {
      return new Response(`后端错误：${backendRes.status}`, { status: backendRes.status });
    }

    // 透传SSE流式响应头
    return new Response(backendRes.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-store",
        "Connection": "keep-alive",
      },
    });
  } catch (err) {
    return new Response("连接后端FastAPI失败，请确认后端服务已经启动", { status: 500 });
  }
}
