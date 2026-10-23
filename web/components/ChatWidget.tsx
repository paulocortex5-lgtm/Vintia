"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { loadSession } from "@/lib/engine";
import { postChat } from "@/lib/chat";

export default function ChatWidget() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Defer marking mounted until after the first client render so the
  // server-rendered HTML (null widget) matches the initial client render,
  // avoiding a hydration mismatch. The state update is scheduled through a
  // timer so the setter is not invoked directly in the effect body.
  useEffect(() => {
    const handle = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(handle);
  }, []);

  const session = mounted ? loadSession() : null;

  const scroll = () => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  };
  useEffect(scroll, [messages, open]);

  // Authenticated users carry their real session id; anonymous visitors get
  // a stable device-scoped id so the chat still works without signing in.
  const userId =
    session?.user?.id ?? `anon-${typeof window !== "undefined" ? (window.localStorage.getItem("vantia_anon_id") || (() => { const id = crypto.randomUUID?.() ?? `anon-${Date.now()}`; window.localStorage.setItem("vantia_anon_id", id); return id; })()) : ""}`;

  // `send` is defined before any early return so the hook always runs in
  // the same order on every render (fixes React #310).
  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    const userMessage = { role: "user", content: text };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");
    setSending(true);
    try {
      const reply = await postChat({ userId, message: text, conversationId: conversationId ?? undefined });
      if (reply.status === "ok" && reply.reply) {
        setConversationId(reply.conversation_id);
        setMessages((msgs) => [...msgs, { role: "assistant", content: reply.reply }]);
      } else {
        setMessages((msgs) => [
          ...msgs,
          {
            role: "assistant",
            content:
              "The assistant is unavailable right now — please try again later.",
          },
        ]);
      }
    } catch {
      setMessages((msgs) => [
        ...msgs,
        {
          role: "assistant",
          content: "Could not reach the assistant — please try again later.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [input, sending, userId, conversationId]);

  return (
    <div className="fixed bottom-5 right-5 z-50">
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-full bg-blue-600 p-3 text-white shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
        aria-label="Open Vantia assistant"
      >
        <span className="sr-only">Open assistant</span>
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>
      {open && (
        <div className="mt-2 w-80 rounded-xl border border-gray-200 bg-white shadow-xl flex flex-col">
          <div className="bg-blue-600 rounded-t-xl p-3 text-white flex items-center justify-between">
            <span className="text-sm font-medium">Vantia assistant</span>
            <button
              onClick={() => setOpen(false)}
              className="text-blue-100 hover:text-white"
              aria-label="Close assistant"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3 text-sm text-gray-700">
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user" ? "text-right text-blue-600" : "text-left text-gray-800"
                }
              >
                {m.content}
              </div>
            ))}
            <div ref={endRef} />
          </div>
          <div className="p-3 border-t border-gray-200 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask about jobs, scholarships, CV..."
              disabled={sending}
              className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="rounded bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
