// API client for MindSync backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("mindsync_token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Don't set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("mindsync_token");
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export const api = new ApiClient();

// Type-safe API functions
export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/api/auth/login", { email, password }),
};

export const documentsApi = {
  list: () => api.get<Document[]>("/api/documents"),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<DocumentUploadResponse>("/api/documents", formData);
  },
  delete: (id: string) => api.delete<{ status: string; id: string }>(`/api/documents/${id}`),
  fileUrl: (id: string) => {
    const token = localStorage.getItem("mindsync_token");
    return `${API_BASE}/api/documents/${id}/file?token=${token || ""}`;
  },
  fetchFile: (id: string) => {
    const token = localStorage.getItem("mindsync_token");
    return fetch(`${API_BASE}/api/documents/${id}/file?token=${token || ""}`);
  },
};

export const conversationsApi = {
  list: (limit = 50, offset = 0) =>
    api.get<Conversation[]>(`/api/conversations?limit=${limit}&offset=${offset}`),
  messages: (chatId: string) =>
    api.get<Message[]>(`/api/conversations/${chatId}/messages`),
};

export const sessionsApi = {
  start: () => api.post("/api/sessions/start"),
  stop: () => api.post("/api/sessions/stop"),
  restart: () => api.post("/api/sessions/restart"),
  logout: () => api.post("/api/sessions/logout"),
  qr: (name: string) => api.get<{ qr: string | null }>(`/api/sessions/${name}/qr`),
  status: (name: string) => api.get<SessionStatus>(`/api/sessions/${name}/status`),
};

export const playgroundApi = {
  listSessions: () => api.get<PlaygroundSession[]>("/api/playground/sessions"),
  createSession: (title = "New Chat") =>
    api.post<PlaygroundSession>("/api/playground/sessions", { title }),
  deleteSession: (id: string) =>
    api.delete<{ status: string; id: string }>(`/api/playground/sessions/${id}`),
  messages: (sessionId: string) =>
    api.get<Message[]>(`/api/playground/sessions/${sessionId}/messages`),
  stream: async function* (
    sessionId: string,
    query: string,
    includeSources = true,
  ): AsyncGenerator<{ type: string; content?: string; sources?: ChatResponse["sources"] }> {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("mindsync_token")
        : null;
    const res = await fetch(`${API_BASE}/api/playground/sessions/${sessionId}/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query, include_sources: includeSources }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`Stream request failed: ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const payload = JSON.parse(line.slice(6));
          yield payload;
        } catch {
          /* skip malformed lines */
        }
      }
    }
  },
};

export const settingsApi = {
  get: () => api.get<Record<string, string>>("/api/settings"),
  update: (key: string, value: string) =>
    api.put<{ status: string; key: string }>("/api/settings", { key, value }),
};

export const statsApi = {
  get: () => api.get<DashboardStats>("/api/stats"),
};

// Types
export interface Document {
  id: string;
  name: string;
  source: string;
  status: "pending" | "processing" | "done" | "failed";
  chunk_count: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  id: string;
  name: string;
  status: string;
  chunks: number;
}

export interface Conversation {
  id: string;
  chat_id: string;
  contact_name: string;
  last_message_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SessionStatus {
  name: string;
  status: string;
  me?: {
    id: string;
    pushName?: string;
  } | null;
  engine?: {
    engine?: string;
    WWebVersion?: string;
    state?: string;
  };
  config?: {
    webhooks?: Array<{
      url: string;
      events: string[];
    }>;
  };
}

export interface ChatResponse {
  answer: string;
  sources: Array<{
    text: string;
    score: number;
    source: string;
    document_id: string;
    chunk_index: number;
  }>;
}

export interface PlaygroundSession {
  id: string;
  title: string;
  last_message_at: string | null;
  created_at: string | null;
}

export interface DashboardStats {
  total_messages: number;
  total_conversations: number;
  total_documents: number;
}
