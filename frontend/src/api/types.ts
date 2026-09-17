export type DocumentStatus = "uploading" | "queued" | "processing" | "ready" | "failed";

export interface User {
  id: string;
  email: string;
  name: string;
  picture: string | null;
}

export interface PublicConfig {
  max_upload_mb: number;
  max_pages: number;
  google_enabled: boolean;
  dev_login_enabled: boolean;
  ai_enabled: boolean;
}

export interface PaperDocument {
  id: string;
  name: string;
  status: DocumentStatus;
  size: number | null;
  pages: number | null;
  chunk_count: number | null;
  error: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface Source {
  page: number;
  text: string;
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export type AnswerMode = "llm" | "extractive" | "none";

export interface Answer {
  answer: string;
  sources: Source[];
  mode: AnswerMode;
}

const PENDING_STATUSES: DocumentStatus[] = ["uploading", "queued", "processing"];

export function isPending(status: DocumentStatus): boolean {
  return PENDING_STATUSES.includes(status);
}
