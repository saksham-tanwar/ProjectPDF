import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { AnswerMode, ConversationTurn, Source } from "../api/types";
import { readSession, removeSession, writeSession } from "./storage";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  status: "pending" | "done" | "error";
  sources?: Source[];
  mode?: AnswerMode;
  question?: string;
}

const HISTORY_TURNS = 6;
const TURN_MAX_CHARS = 4000;

/** The last few completed exchanges, so the API can resolve follow-ups like "what about the second one?". */
export function historyFor(messages: ChatMessage[]): ConversationTurn[] {
  return messages
    .filter((message) => message.status === "done" && message.text.trim() && message.mode !== "none")
    .slice(-HISTORY_TURNS)
    .map((message) => ({ role: message.role, content: message.text.slice(0, TURN_MAX_CHARS) }));
}

const storageKey = (documentId: string) => `paperchat:conversation:${documentId}`;

export function clearConversation(documentId: string) {
  removeSession(storageKey(documentId));
}

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

/** One conversation per document, kept for the life of the browser tab. Mount with key={documentId}. */
export function useConversation(documentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    // A reload mid-request leaves a pending bubble behind; drop it rather than spin forever.
    readSession<ChatMessage[]>(storageKey(documentId), []).filter((message) => message.status !== "pending"),
  );

  useEffect(() => {
    writeSession(storageKey(documentId), messages.filter((message) => message.status !== "pending"));
  }, [documentId, messages]);

  const busy = messages.some((message) => message.status === "pending");
  const messagesRef = useRef(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const ask = useCallback(
    async (question: string, replaceId?: string) => {
      const pendingId = newId();
      const current = messagesRef.current;
      // On retry, the question being retried is already in the list; only send what came before it.
      const failedIndex = replaceId ? current.findIndex((message) => message.id === replaceId) : -1;
      const history = historyFor(failedIndex > 0 ? current.slice(0, failedIndex - 1) : current);
      setMessages((current) => {
        const withoutFailed = replaceId ? current.filter((message) => message.id !== replaceId) : current;
        const userMessage: ChatMessage = { id: newId(), role: "user", text: question, status: "done" };
        const pending: ChatMessage = { id: pendingId, role: "assistant", text: "", status: "pending", question };
        return replaceId ? [...withoutFailed, pending] : [...withoutFailed, userMessage, pending];
      });
      try {
        const answer = await api.ask(documentId, question, history);
        setMessages((current) =>
          current.map((message) =>
            message.id === pendingId
              ? { ...message, text: answer.answer, sources: answer.sources, mode: answer.mode, status: "done" }
              : message,
          ),
        );
      } catch (error) {
        const text = error instanceof Error ? error.message : "Something went wrong. Please try again.";
        setMessages((current) =>
          current.map((message) => (message.id === pendingId ? { ...message, text, status: "error" } : message)),
        );
      }
    },
    [documentId],
  );

  const clear = useCallback(() => setMessages([]), []);

  return { messages, busy, ask, clear };
}
