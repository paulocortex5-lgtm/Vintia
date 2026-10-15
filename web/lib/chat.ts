/** Thin client for the platform chatbot endpoint (``POST /chat`` on the engine). */
import { ENGINE } from "./engine";

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ChatReply = {
  status: string;
  reply: string;
  conversation_id: string;
  tier: string;
  used_today: number;
  limit: number | null;
};

export async function postChat({
  userId,
  message,
  conversationId,
}: {
  userId: string;
  message: string;
  conversationId?: string;
}): Promise<ChatReply> {
  const response = await fetch(`${ENGINE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      message,
      conversation_id: conversationId,
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: { message?: string };
    };
    throw new Error(
      body.detail?.message || `Chat request failed (${response.status})`,
    );
  }
  return (await response.json()) as ChatReply;
}
