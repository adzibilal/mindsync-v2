"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { conversationsApi } from "@/lib/api";
import type { Conversation, Message } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Bot, User, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/app/markdown-content";

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMin / 60);
  const diffD = Math.floor(diffH / 24);
  if (diffMin < 1) return "Baru saja";
  if (diffMin < 60) return `${diffMin}m`;
  if (diffH < 24) return `${diffH}h`;
  if (diffD < 7) return `${diffD}d`;
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

function getInitial(name: string | null, chatId: string): string {
  const label = name || chatId;
  return label.charAt(0).toUpperCase();
}

export default function ConversationsPage() {
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(),
    refetchInterval: 15_000,
  });

  const { data: messages, isLoading: messagesLoading } = useQuery({
    queryKey: ["messages", selectedChatId],
    queryFn: () => conversationsApi.messages(selectedChatId!),
    enabled: !!selectedChatId,
    refetchInterval: 5_000,
  });

  const selectedConv = conversations?.find((c: Conversation) => c.chat_id === selectedChatId);

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-6">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          Conversations
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          WhatsApp chat history
        </p>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden rounded-xl bg-card">
        {/* Chat list */}
        <div className="flex min-h-0 w-80 shrink-0 flex-col border-r border-border">
          <div className="border-b border-border px-5 py-4">
            <h3 className="font-heading text-[16px] font-[900] text-ink">
              Chats
            </h3>
            {conversations && (
              <p className="mt-0.5 text-[12px] font-semibold text-muted-foreground">
                {conversations.length} conversation{conversations.length > 1 ? "s" : ""}
              </p>
            )}
          </div>
          <ScrollArea className="min-h-0 flex-1">
            {isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-xl p-3">
                    <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-28" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                  </div>
                ))}
              </div>
            ) : conversations && conversations.length > 0 ? (
              <div className="p-2">
                {conversations.map((conv: Conversation) => {
                  const active = selectedChatId === conv.chat_id;
                  return (
                    <button
                      key={conv.id}
                      onClick={() => setSelectedChatId(conv.chat_id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors",
                        active
                          ? "bg-primary-pale"
                          : "hover:bg-canvas-soft"
                      )}
                    >
                      <div
                        className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-[14px] font-[900]",
                          active ? "bg-primary text-ink" : "bg-canvas-soft text-ink"
                        )}
                      >
                        {getInitial(conv.contact_name, conv.chat_id)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between">
                          <span className={cn(
                            "truncate text-[14px] font-semibold",
                            active ? "text-ink" : "text-ink"
                          )}>
                            {conv.contact_name || conv.chat_id}
                          </span>
                          <span className="ml-2 shrink-0 text-[11px] font-semibold text-muted-foreground">
                            {relativeTime(conv.last_message_at)}
                          </span>
                        </div>
                        <p className="mt-0.5 truncate text-[12px] text-muted-foreground">
                          {conv.chat_id}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-canvas-soft">
                  <MessageSquare className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="mt-4 text-[14px] font-semibold text-muted-foreground">
                  No conversations yet
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  Send a message on WhatsApp to start
                </p>
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Message thread */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {/* Thread header */}
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            {selectedConv ? (
              <>
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-pale text-[14px] font-[900] text-ink">
                  {getInitial(selectedConv.contact_name, selectedConv.chat_id)}
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-ink">
                    {selectedConv.contact_name || selectedConv.chat_id}
                  </p>
                  <p className="text-[12px] text-muted-foreground">
                    {selectedConv.chat_id}
                  </p>
                </div>
              </>
            ) : (
              <div>
                <p className="text-[14px] font-semibold text-ink">
                  Select a conversation
                </p>
                <p className="text-[12px] text-muted-foreground">
                  Choose from the list on the left
                </p>
              </div>
            )}
          </div>

          {/* Messages */}
          <ScrollArea className="min-h-0 flex-1">
            {!selectedChatId ? (
              <div className="flex h-full flex-col items-center justify-center py-20">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-canvas-soft">
                  <MessageSquare className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="mt-4 text-[14px] font-semibold text-muted-foreground">
                  No conversation selected
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  Pick a chat from the left panel
                </p>
              </div>
            ) : messagesLoading ? (
              <div className="space-y-4 p-6">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className={cn("flex", i % 2 === 0 ? "justify-start" : "justify-end")}>
                    <Skeleton className={cn("h-16", i % 2 === 0 ? "w-[70%] rounded-2xl rounded-bl-md" : "w-[60%] rounded-2xl rounded-br-md")} />
                  </div>
                ))}
              </div>
            ) : messages && messages.length > 0 ? (
              <div className="space-y-4 p-6">
                {messages.map((msg: Message) => {
                  const isUser = msg.role === "user";
                  return (
                    <div key={msg.id} className={cn("flex gap-2.5", isUser ? "justify-end" : "justify-start")}>
                      {!isUser && (
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-canvas-soft">
                          <Bot className="h-3.5 w-3.5 text-ink" />
                        </div>
                      )}
                      <div className="max-w-[75%]">
                        <div
                          className={cn(
                            "px-4 py-2.5 text-[14px] leading-relaxed",
                            isUser
                              ? "rounded-2xl rounded-br-md bg-primary text-ink"
                              : "rounded-2xl rounded-bl-md bg-canvas-soft text-ink overflow-hidden"
                          )}
                        >
                          {isUser ? (
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          ) : (
                            <MarkdownContent content={msg.content} />
                          )}
                        </div>
                        {msg.created_at && (
                          <p className={cn(
                            "mt-1 text-[11px] font-semibold text-muted-foreground",
                            isUser ? "text-right" : "text-left"
                          )}>
                            {new Date(msg.created_at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        )}
                      </div>
                      {isUser && (
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary-pale">
                          <User className="h-3.5 w-3.5 text-ink" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center py-20">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-canvas-soft">
                  <MessageSquare className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="mt-4 text-[14px] font-semibold text-muted-foreground">
                  No messages yet
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  This conversation is empty
                </p>
              </div>
            )}
          </ScrollArea>
        </div>
      </div>
    </div>
  );
}
