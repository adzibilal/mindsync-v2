"use client";

import { useQuery } from "@tanstack/react-query";
import { statsApi, documentsApi, sessionsApi } from "@/lib/api";
import { MessageSquare, BookOpen, Users, Smartphone } from "lucide-react";

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl bg-card p-6">
      <div className="flex items-center justify-between">
        <span className="text-[14px] font-semibold text-muted-foreground">{label}</span>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-pale">
          <Icon className="h-5 w-5 text-ink" />
        </div>
      </div>
      <p className="mt-3 font-heading text-[40px] font-[900] leading-none tracking-tight text-ink">
        {value}
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: statsApi.get,
    refetchInterval: 30_000,
  });

  const { data: documents } = useQuery({
    queryKey: ["documents"],
    queryFn: documentsApi.list,
  });

  const { data: sessionStatus } = useQuery({
    queryKey: ["session-status"],
    queryFn: () => sessionsApi.status("default"),
    retry: false,
  });

  const isOpen = sessionStatus?.status === "OPEN";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          Dashboard
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          Overview MindSync RAG Bot
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={MessageSquare}
          label="Total Messages"
          value={stats?.total_messages ?? "—"}
        />
        <StatCard
          icon={Users}
          label="Conversations"
          value={stats?.total_conversations ?? "—"}
        />
        <StatCard
          icon={BookOpen}
          label="Documents"
          value={stats?.total_documents ?? "—"}
        />
        <div className="rounded-xl bg-card p-6">
          <div className="flex items-center justify-between">
            <span className="text-[14px] font-semibold text-muted-foreground">
              WA Session
            </span>
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-pale">
              <Smartphone className="h-5 w-5 text-ink" />
            </div>
          </div>
          <div className="mt-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold ${
                isOpen
                  ? "bg-primary-pale text-positive-deep"
                  : "bg-negative-bg text-white"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  isOpen ? "bg-positive" : "bg-negative"
                }`}
              />
              {sessionStatus?.status ?? "Unknown"}
            </span>
          </div>
        </div>
      </div>

      <div className="rounded-xl bg-card p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-heading text-[20px] font-[900] text-ink">
            Recent Documents
          </h2>
        </div>
        {documents && documents.length > 0 ? (
          <div className="space-y-0">
            {documents.slice(0, 5).map((doc, i) => (
              <div
                key={doc.id}
                className={`flex items-center justify-between py-3 ${
                  i > 0 ? "border-t border-border" : ""
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-canvas-soft">
                    <BookOpen className="h-5 w-5 text-ink" />
                  </div>
                  <span className="text-[14px] font-semibold text-ink">
                    {doc.name}
                  </span>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-[12px] font-semibold ${
                    doc.status === "done"
                      ? "bg-primary-pale text-positive-deep"
                      : doc.status === "failed"
                      ? "bg-negative-bg text-white"
                      : "bg-canvas-soft text-muted-foreground"
                  }`}
                >
                  {doc.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-[14px] text-muted-foreground">
            No documents uploaded yet.
          </p>
        )}
      </div>
    </div>
  );
}
