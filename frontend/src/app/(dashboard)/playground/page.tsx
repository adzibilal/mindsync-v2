"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { playgroundApi, type ChatResponse, type PlaygroundSession } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Send, Bot, User, BookOpen, X, Sparkles, Plus, Trash2, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/app/markdown-content";
import { toast } from "sonner";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatResponse["sources"];
  streaming?: boolean;
}

const SUGGESTED_PROMPTS = [
  "Apa itu sistem RAG?",
  "Bagaimana cara kerja embedding?",
  "Jelaskan tentang similarity search",
];

const ACTIVE_KEY = "mindsync_playground_active";

export default function PlaygroundPage() {
  const [sessions, setSessions] = useState<PlaygroundSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedSources, setSelectedSources] = useState<ChatResponse["sources"] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load sessions on mount
  useEffect(() => {
    (async () => {
      try {
        const list = await playgroundApi.listSessions();
        setSessions(list);
        const stored = typeof window !== "undefined" ? localStorage.getItem(ACTIVE_KEY) : null;
        const pick = list.find((s) => s.id === stored)?.id ?? list[0]?.id ?? null;
        if (pick) {
          setActiveId(pick);
        } else {
          // Auto-create first session
          const fresh = await playgroundApi.createSession();
          setSessions([fresh]);
          setActiveId(fresh.id);
        }
      } catch (err) {
        toast.error("Gagal memuat sesi playground");
        console.error(err);
      }
    })();
  }, []);

  // Persist active session
  useEffect(() => {
    if (activeId && typeof window !== "undefined") {
      localStorage.setItem(ACTIVE_KEY, activeId);
    }
  }, [activeId]);

  // Load messages when active session changes
  useEffect(() => {
    if (!activeId) return;
    (async () => {
      try {
        const msgs = await playgroundApi.messages(activeId);
        setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
        setSelectedSources(null);
      } catch (err) {
        console.error(err);
        setMessages([]);
      }
    })();
  }, [activeId]);

  const handleNewChat = async () => {
    // Reuse an existing empty (untitled) session instead of stacking duplicate "New Chat" entries.
    const existingEmpty = sessions.find((s) => !s.title);
    if (existingEmpty) {
      setActiveId(existingEmpty.id);
      setMessages([]);
      setSelectedSources(null);
      return;
    }
    try {
      const fresh = await playgroundApi.createSession();
      setSessions((prev) => [fresh, ...prev]);
      setActiveId(fresh.id);
      setMessages([]);
      setSelectedSources(null);
    } catch (err) {
      toast.error("Gagal membuat sesi baru");
      console.error(err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Hapus sesi ini?")) return;
    try {
      await playgroundApi.deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);
      if (activeId === id) {
        if (remaining[0]) {
          setActiveId(remaining[0].id);
        } else {
          const fresh = await playgroundApi.createSession();
          setSessions([fresh]);
          setActiveId(fresh.id);
        }
      }
      toast.success("Sesi dihapus");
    } catch (err) {
      toast.error("Gagal menghapus sesi");
      console.error(err);
    }
  };

  const handleSubmit = async (e: React.FormEvent, prompt?: string) => {
    e.preventDefault();
    const q = (prompt || query).trim();
    if (!q || loading || !activeId) return;

    setQuery("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    let accContent = "";
    let accSources: ChatResponse["sources"] = [];

    try {
      for await (const event of playgroundApi.stream(activeId, q, true)) {
        if (event.type === "sources" && event.sources) {
          accSources = event.sources;
        } else if (event.type === "token" && event.content) {
          accContent += event.content;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last.role === "assistant") {
              next[next.length - 1] = { ...last, content: accContent, sources: accSources };
            }
            return next;
          });
        } else if (event.type === "error") {
          accContent += `\n\n[Error: ${event.content}]`;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last.role === "assistant") {
              next[next.length - 1] = { ...last, content: accContent };
            }
            return next;
          });
        }
      }
    } catch (err) {
      accContent = err instanceof Error ? err.message : "Terjadi kesalahan";
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last.role === "assistant") {
          next[next.length - 1] = { ...last, content: accContent };
        }
        return next;
      });
    } finally {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last.role === "assistant") {
          next[next.length - 1] = { ...last, streaming: false };
        }
        return next;
      });
      setLoading(false);
      // Refresh sessions to pick up auto-title from backend
      try {
        const list = await playgroundApi.listSessions();
        setSessions(list);
      } catch {
        /* ignore */
      }
    }
  };

  const isStreaming = loading && messages.some((m) => m.streaming);

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-6">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          Playground
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          Test RAG pipeline directly
        </p>
      </div>

      <div className="flex flex-1 gap-4 min-h-0 overflow-hidden">
        {/* Sessions sidebar */}
        <div className="flex w-72 shrink-0 flex-col overflow-hidden rounded-xl bg-card">
          <div className="border-b border-border p-3">
            <Button
              onClick={handleNewChat}
              className="w-full justify-start gap-2"
              variant="outline"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {sessions.filter((s) => s.title).length === 0 ? (
              <div className="py-8 text-center text-[13px] text-muted-foreground">
                Belum ada sesi
              </div>
            ) : (
              <ul className="space-y-1">
                {sessions.filter((s) => s.title).map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => setActiveId(s.id)}
                      className={cn(
                        "group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] transition-colors",
                        activeId === s.id
                          ? "bg-canvas-soft text-ink"
                          : "text-body hover:bg-canvas-soft/60"
                      )}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <span className="flex-1 truncate font-semibold">
                        {s.title || "New Chat"}
                      </span>
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(s.id);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.stopPropagation();
                            handleDelete(s.id);
                          }
                        }}
                        className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Chat panel */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-xl bg-card">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-6">
              {messages.length === 0 && !loading ? (
                <div className="flex flex-col items-center justify-center py-20">
                  <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-primary-pale">
                    <Sparkles className="h-7 w-7 text-positive" />
                  </div>
                  <h3 className="mt-5 font-heading text-[20px] font-[900] text-ink">
                    Ask anything
                  </h3>
                  <p className="mt-1 text-[14px] text-muted-foreground">
                    Get answers from your knowledge base
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => handleSubmit(new Event("click") as unknown as React.FormEvent, prompt)}
                        className="rounded-xl border border-border px-4 py-2 text-[13px] font-semibold text-ink transition-colors hover:bg-canvas-soft"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-5">
                  {messages.map((msg, i) => (
                    <div key={i} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>
                      {msg.role === "assistant" && (
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-canvas-soft">
                          <Bot className="h-4 w-4 text-ink" />
                        </div>
                      )}
                      <div className="max-w-[75%] space-y-1.5">
                        <div
                          className={cn(
                            "px-4 py-2.5 text-[14px] leading-relaxed",
                            msg.role === "user"
                              ? "rounded-2xl rounded-br-md bg-primary text-primary-foreground"
                              : "rounded-2xl rounded-bl-md bg-canvas-soft text-ink overflow-hidden"
                          )}
                        >
                          {msg.role === "assistant" ? (
                            <>
                              <MarkdownContent content={msg.content || " "} />
                              {msg.streaming && (
                                <span className="inline-block h-4 w-[2px] animate-pulse bg-ink align-middle" />
                              )}
                            </>
                          ) : (
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          )}
                        </div>
                        {msg.role === "assistant" && !msg.streaming && msg.sources && msg.sources.length > 0 && (
                          <button
                            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-[12px] font-semibold text-muted-foreground transition-colors hover:bg-canvas-soft hover:text-ink"
                            onClick={() => setSelectedSources(msg.sources!)}
                          >
                            <BookOpen className="h-3 w-3" />
                            {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""}
                          </button>
                        )}
                      </div>
                      {msg.role === "user" && (
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-pale">
                          <User className="h-4 w-4 text-ink" />
                        </div>
                      )}
                    </div>
                  ))}
                  <div ref={scrollRef} />
                </div>
              )}
            </div>
          </div>

          {/* Input */}
          <div className="border-t border-border p-4">
            <form onSubmit={handleSubmit} className="flex items-center gap-3">
              <Input
                placeholder={activeId ? "Ask a question..." : "Loading session..."}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isStreaming || !activeId}
                className="flex-1"
              />
              <Button
                type="submit"
                disabled={isStreaming || !query.trim() || !activeId}
                className="h-12 w-12 shrink-0 px-0"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>

        {/* Sources panel */}
        {selectedSources && (
          <div className="flex w-96 shrink-0 flex-col overflow-hidden rounded-xl bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h3 className="font-heading text-[16px] font-[900] text-ink">
                Retrieved Sources
              </h3>
              <button
                onClick={() => setSelectedSources(null)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-canvas-soft hover:text-ink"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <div className="space-y-3 p-4">
                {selectedSources.map((src, i) => (
                  <div key={i} className="rounded-xl border border-border p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        {src.source || "Unknown"}
                      </Badge>
                      <span className="text-[11px] font-semibold tabular-nums text-muted-foreground">
                        {(src.score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-body whitespace-pre-wrap line-clamp-6">
                      {src.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
