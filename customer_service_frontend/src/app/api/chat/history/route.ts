import type { NextRequest } from 'next/server';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const threadId = searchParams.get('thread_id');

  if (!threadId) {
    return Response.json({ messages: [] });
  }

  try {
    const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    const backendRes = await fetch(
      `${BACKEND}/api/chat/history?thread_id=${encodeURIComponent(threadId)}`,
      { cache: 'no-store' }
    );

    if (!backendRes.ok) {
      return Response.json({ messages: [] }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return Response.json(data);
  } catch (err) {
    console.error('[History] 请求后端失败', err);
    return Response.json({ messages: [] }, { status: 500 });
  }
}