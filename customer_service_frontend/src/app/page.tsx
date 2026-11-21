// customer_service_frontend/src/app/page.tsx
'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const aiContentRef = useRef('');

  // 用 sessionStorage 持久化 threadId，避免多标签页串台
  const getThreadId = useCallback(() => {
    if (typeof window === 'undefined') return 'ssr';
    let id = sessionStorage.getItem('thread_id');
    if (!id) {
      id = `user_${Math.random().toString(36).substring(2, 10)}`;
      sessionStorage.setItem('thread_id', id);
    }
    return id;
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 【新增】启动时拉取历史消息
  const loadHistory = useCallback(async () => {
    const tid = getThreadId();
    if (tid === 'ssr') return;
    try {
      const res = await fetch(`/api/chat/history?thread_id=${tid}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages);
      }
    } catch (e) {
      console.warn('[History] 加载失败', e);
    } finally {
      setHistoryLoaded(true);
    }
  }, [getThreadId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSSEData = useCallback((data: any, setReceivedDone: (v: boolean) => void) => {
    if (data.type === 'status') {
      setStatusText(data.content);
    } else if (data.type === 'token') {
      setStatusText('');
      aiContentRef.current += data.content;
      setMessages((prev) => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = aiContentRef.current;
        return newMsgs;
      });
    } else if (data.type === 'done') {
      setReceivedDone(true);
      setIsLoading(false);
    } else if (data.type === 'error') {
      setStatusText('发生错误: ' + data.content);
      setIsLoading(false);
    }
  }, []);

  const parseSSEChunk = useCallback(
    (raw: string, setReceivedDone: (v: boolean) => void) => {
      const blocks = raw.split('\n\n');
      for (const block of blocks) {
        if (!block.startsWith('data: ')) continue;
        const dataStr = block.slice(6).trim();
        if (!dataStr) continue;
        try {
          handleSSEData(JSON.parse(dataStr), setReceivedDone);
        } catch (e) {
          console.warn('[SSE] 解析失败:', e, dataStr);
        }
      }
    },
    [handleSSEData]
  );

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    setStatusText('正在思考...');
    aiContentRef.current = '';
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let receivedDone = false;
    const setReceivedDone = (v: boolean) => {
      receivedDone = v;
    };

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 【修复】用 getThreadId() 而不是 ref，避免 SSR 时残留 'ssr'
        body: JSON.stringify({ message: userMsg, thread_id: getThreadId() }),
        signal: controller.signal,
      });

      if (!response.body) throw new Error('没有返回流');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        parseSSEChunk(parts.join('\n\n'), setReceivedDone);
      }

      if (buffer.trim()) {
        parseSSEChunk(buffer, setReceivedDone);
        buffer = '';
      }

      if (!receivedDone) {
        console.warn('[SSE] 流结束但未收到 done 事件');
        setIsLoading(false);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error(err);
        setStatusText('连接服务器失败');
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsLoading(false);
      }
    }
  }, [input, isLoading, parseSSEChunk, getThreadId]);

  return (
    <div className="w-full h-screen flex flex-col bg-gray-100">
      <header className="bg-white shadow-sm p-4 text-center">
        <h1 className="text-xl font-bold text-gray-800">电商智能客服 </h1>
        <p className="text-xs text-gray-500 mt-1">基于 LangGraph 多智能体架构</p>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 【修复】历史加载完再判断是否需要显示空状态提示 */}
        {messages.length === 0 && historyLoaded && (
          <div className="text-center text-gray-400 mt-20">
            你好！我是智能客服，有什么可以帮您？
            <br />
            试试问："帮我查一下订单 ORD-001 的物流"
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[75%] p-3 rounded-lg text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-gray-800 shadow-sm rounded-bl-none border border-gray-100'
              }`}
            >
              {msg.content ||
                (isLoading &&
                  index === messages.length - 1 && (
                    <span className="text-gray-400 animate-pulse">正在生成...</span>
                  ))}
            </div>
          </div>
        ))}

        {statusText && (
          <div className="flex justify-start">
            <div className="text-xs text-blue-500 bg-blue-50 px-3 py-1 rounded-full animate-pulse">
              ⚙️ {statusText}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="bg-white p-4 border-t">
        <div className="max-w-4xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="请输入您的问题..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition-colors disabled:bg-gray-400"
          >
            发送
          </button>
        </div>
      </footer>
    </div>
  );
}