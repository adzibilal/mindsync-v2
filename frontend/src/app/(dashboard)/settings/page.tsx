"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Save } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      settingsApi.update(key, value),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(`Saved ${vars.key}`);
    },
    onError: (err: Error) => toast.error(`Failed: ${err.message}`),
  });

  const handleSave = (key: string) => {
    if (form[key] !== undefined) {
      saveMutation.mutate({ key, value: form[key] });
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
            Settings
          </h1>
          <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
            Configure the RAG pipeline
          </p>
        </div>
        <Card>
          <CardContent className="space-y-4 pt-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          Settings
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          Configure the RAG pipeline
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System Prompt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            rows={4}
            value={form.system_prompt || ""}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="Kamu adalah asisten yang menjawab pertanyaan..."
          />
          <Button onClick={() => handleSave("system_prompt")} disabled={saveMutation.isPending}>
            <Save className="mr-2 h-4 w-4" /> Save
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
