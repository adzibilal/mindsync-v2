"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { sessionsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { LogOut, Power, PowerOff, QrCode, RefreshCw, RotateCw } from "lucide-react";
import { toast } from "sonner";

function statusVariant(status?: string): "positive" | "negative" | "outline" {
  if (status === "WORKING") return "positive";
  if (status === "FAILED") return "negative";
  return "outline";
}

function formatNumber(meId?: string | null): string {
  if (!meId) return "—";
  return "+" + meId.replace(/@.*$/, "");
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold text-ink text-right truncate">{value}</span>
    </div>
  );
}

export default function SessionsPage() {
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["session-status"],
    queryFn: () => sessionsApi.status("default"),
    // poll fast while connecting, slow once connected
    refetchInterval: (q) =>
      (q.state.data as { status?: string } | undefined)?.status === "WORKING" ? 15_000 : 3_000,
    retry: false,
  });

  const connected = status?.status === "WORKING";
  const needsQr = status?.status === "SCAN_QR_CODE";

  const { data: qrData } = useQuery({
    queryKey: ["session-qr"],
    queryFn: () => sessionsApi.qr("default"),
    // WhatsApp rotates the QR ~every 20s; poll fast so the UI never shows an expired one.
    refetchInterval: () => (needsQr ? 2_000 : false),
    refetchIntervalInBackground: true,
    staleTime: 0,
    retry: false,
    enabled: needsQr,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["session-status"] });
    queryClient.invalidateQueries({ queryKey: ["session-qr"] });
  };

  const action = (label: string) => ({
    onSuccess: () => {
      refresh();
      toast.success(`${label} session`);
    },
    onError: (err: Error) => toast.error(`Failed: ${err.message}`),
  });

  const startMutation = useMutation({ mutationFn: sessionsApi.start, ...action("Started") });
  const stopMutation = useMutation({ mutationFn: sessionsApi.stop, ...action("Stopped") });
  const restartMutation = useMutation({ mutationFn: sessionsApi.restart, ...action("Restarted") });
  const logoutMutation = useMutation({ mutationFn: sessionsApi.logout, ...action("Logged out") });

  const anyPending =
    startMutation.isPending ||
    stopMutation.isPending ||
    restartMutation.isPending ||
    logoutMutation.isPending;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
          WhatsApp Session
        </h1>
        <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
          Manage WAHA WhatsApp connection
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Session details */}
        <Card>
          <CardHeader>
            <CardTitle>Session Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <>
                <div className="space-y-3">
                  <Row
                    label="Status"
                    value={
                      <Badge variant={statusVariant(status?.status)}>
                        {status?.status ?? "Unknown"}
                      </Badge>
                    }
                  />
                  <Row label="Session" value={<span className="font-mono">{status?.name ?? "default"}</span>} />
                  {connected && (
                    <>
                      <Row label="Number" value={<span className="font-mono">{formatNumber(status?.me?.id)}</span>} />
                      <Row label="Name" value={status?.me?.pushName || "—"} />
                    </>
                  )}
                  <Row label="Engine" value={status?.engine?.engine || "—"} />
                  {status?.engine?.state && <Row label="Engine state" value={status.engine.state} />}
                  {status?.config?.webhooks?.[0]?.url && (
                    <div className="space-y-1 pt-1">
                      <span className="text-sm text-muted-foreground">Webhook</span>
                      <p className="break-all rounded-lg bg-canvas-soft px-3 py-2 font-mono text-[12px] text-ink">
                        {status.config.webhooks[0].url}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    onClick={() => startMutation.mutate()}
                    disabled={anyPending || connected}
                  >
                    <Power className="mr-2 h-4 w-4" />
                    {startMutation.isPending ? "Starting..." : "Start"}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => restartMutation.mutate()}
                    disabled={anyPending}
                  >
                    <RotateCw className="mr-2 h-4 w-4" />
                    {restartMutation.isPending ? "Restarting..." : "Restart"}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => stopMutation.mutate()}
                    disabled={anyPending || status?.status === "STOPPED"}
                  >
                    <PowerOff className="mr-2 h-4 w-4" />
                    {stopMutation.isPending ? "Stopping..." : "Stop"}
                  </Button>
                  {connected && (
                    <Button
                      variant="destructive"
                      onClick={() => {
                        if (confirm("Logout & putuskan WhatsApp dari sesi ini? Perlu scan QR lagi untuk konek.")) {
                          logoutMutation.mutate();
                        }
                      }}
                      disabled={anyPending}
                    >
                      <LogOut className="mr-2 h-4 w-4" />
                      {logoutMutation.isPending ? "Logging out..." : "Logout"}
                    </Button>
                  )}
                  <Button variant="tertiary" onClick={refresh} disabled={anyPending}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* QR — only while waiting to scan */}
        {needsQr && (
          <Card>
            <CardHeader>
              <CardTitle>QR Code</CardTitle>
            </CardHeader>
            <CardContent className="flex min-h-[250px] items-center justify-center">
              {qrData?.qr ? (
                <div className="text-center">
                  <img src={qrData.qr} alt="QR Code" className="max-w-[250px] rounded-lg" />
                  <p className="mt-3 text-[13px] text-muted-foreground">
                    Scan via WhatsApp → Linked Devices
                  </p>
                </div>
              ) : (
                <div className="text-center text-muted-foreground">
                  <QrCode className="mx-auto mb-2 h-16 w-16 opacity-30" />
                  <p>Loading QR…</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
