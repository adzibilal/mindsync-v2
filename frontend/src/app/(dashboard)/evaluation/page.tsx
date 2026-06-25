"use client";

import { useQuery } from "@tanstack/react-query";
import { evaluationApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, HelpCircle } from "lucide-react";

export default function EvaluationPage() {
  const { data: top, isLoading: topLoading } = useQuery({
    queryKey: ["eval-top"],
    queryFn: evaluationApi.topQuestions,
  });

  const { data: unanswered, isLoading: unansweredLoading } = useQuery({
    queryKey: ["eval-unanswered"],
    queryFn: evaluationApi.unanswered,
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          Evaluasi
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          Bahan perbaikan knowledge base dari pertanyaan mahasiswa
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Top questions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" /> Pertanyaan Terbanyak
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : top && top.length > 0 ? (
              <ul className="space-y-1">
                {top.map((q, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 hover:bg-canvas-soft"
                  >
                    <span className="text-[14px] text-ink line-clamp-2">{q.question}</span>
                    <span className="shrink-0 rounded-full bg-primary-pale px-2.5 py-0.5 text-[12px] font-[900] text-positive-deep tabular-nums">
                      {q.count}×
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-8 text-center text-[14px] text-muted-foreground">
                Belum ada pertanyaan.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Unanswered */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4" /> Belum Terjawab
            </CardTitle>
          </CardHeader>
          <CardContent>
            {unansweredLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : unanswered && unanswered.length > 0 ? (
              <ul className="space-y-1">
                {unanswered.map((q, i) => (
                  <li key={i} className="rounded-lg px-3 py-2 hover:bg-canvas-soft">
                    <p className="text-[14px] text-ink line-clamp-2">{q.question}</p>
                    {q.answered_at && (
                      <p className="mt-0.5 text-[12px] text-muted-foreground">
                        {new Date(q.answered_at).toLocaleString("id-ID")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-8 text-center text-[14px] text-muted-foreground">
                Tidak ada pertanyaan yang gagal dijawab. 🎉
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
