import type { Answer, ConversationTurn, PaperDocument, PublicConfig, User } from "./types";

/** Empty by default: the app is served from the same origin as the API. */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  401: "Please sign in to continue.",
  403: "You don't have permission to do that.",
  404: "We couldn't find that.",
  413: "That file is too large.",
  429: "You're going a little fast. Please wait a moment and try again.",
  502: "The service is temporarily unreachable. Please try again.",
  503: "The service is temporarily unavailable. Please try again.",
  504: "The request timed out. Please try again.",
};

export function messageFor(status: number, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) return "Please check what you entered and try again.";
  }
  if (status === 0) return "You appear to be offline. Check your connection and try again.";
  return FALLBACK_MESSAGES[status] ?? "Something went wrong. Please try again.";
}

export function parseBody(contentType: string | null, text: string): unknown {
  if (!text || !contentType?.includes("application/json")) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      ...init,
      headers: { Accept: "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, messageFor(0, null));
  }
  const body = parseBody(response.headers.get("content-type"), await response.text());
  if (!response.ok) throw new ApiError(response.status, messageFor(response.status, body));
  return body as T;
}

function send(method: string, payload?: unknown): RequestInit {
  if (payload === undefined) return { method };
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
}

const documentPath = (id: string) => `/api/documents/${encodeURIComponent(id)}`;

export const api = {
  config: () => request<PublicConfig>("/api/config"),

  async me(): Promise<User | null> {
    try {
      return await request<User>("/api/me");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },

  devLogin: () => request<null>("/auth/dev-login", send("POST")),
  logout: () => request<null>("/auth/logout", send("POST")),
  deleteAccount: () => request<null>("/api/me", send("DELETE")),

  listDocuments: () => request<{ documents: PaperDocument[] }>("/api/documents").then((body) => body.documents),
  getDocument: (id: string) => request<PaperDocument>(documentPath(id)),
  deleteDocument: (id: string) => request<null>(documentPath(id), send("DELETE")),
  ask: (id: string, question: string, history: ConversationTurn[] = []) =>
    request<Answer>(`${documentPath(id)}/questions`, send("POST", { question, history })),

  /** Uses XHR rather than fetch so the UI can show real upload progress. */
  uploadDocument(file: File, onProgress: (fraction: number) => void, signal?: AbortSignal): Promise<PaperDocument> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE_URL}/api/documents`);
      xhr.withCredentials = true;
      xhr.setRequestHeader("Accept", "application/json");
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total);
      };
      xhr.onload = () => {
        const body = parseBody(xhr.getResponseHeader("content-type"), xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as PaperDocument);
        else reject(new ApiError(xhr.status, messageFor(xhr.status, body)));
      };
      xhr.onerror = () => reject(new ApiError(0, messageFor(0, null)));
      xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
      signal?.addEventListener("abort", () => xhr.abort(), { once: true });
      const data = new FormData();
      data.append("file", file);
      xhr.send(data);
    });
  },
};

export const googleLoginUrl = `${API_BASE_URL}/auth/google/login`;
