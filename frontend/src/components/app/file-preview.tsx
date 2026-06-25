"use client";

import { useState, useEffect, useCallback } from "react";
import { X, FileText, Download, Loader2, AlertCircle, Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { documentsApi } from "@/lib/api";

const TEXT_EXTENSIONS = ["txt", "md", "json", "csv", "xml", "yaml", "yml", "toml", "ini", "cfg", "log"];
const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico"];
const PDF_EXTENSIONS = ["pdf"];

function getExt(name: string): string {
  return (name.split(".").pop() || "").toLowerCase();
}

function getMediaType(name: string): "image" | "pdf" | "text" | "unknown" {
  const ext = getExt(name);
  if (IMAGE_EXTENSIONS.includes(ext)) return "image";
  if (PDF_EXTENSIONS.includes(ext)) return "pdf";
  if (TEXT_EXTENSIONS.includes(ext)) return "text";
  return "unknown";
}

function FileIcon({ type, className }: { type: string; className?: string }) {
  const ext = getExt(type);
  if (IMAGE_EXTENSIONS.includes(ext)) return <ImageIcon className={className} />;
  return <FileText className={className} />;
}

interface FilePreviewProps {
  documentId: string;
  fileName: string;
  open: boolean;
  onClose: () => void;
}

export function FilePreview({ documentId, fileName, open, onClose }: FilePreviewProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  const mediaType = getMediaType(fileName);

  const loadFile = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await documentsApi.fetchFile(documentId);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      if (mediaType === "text") {
        const text = await res.text();
        setContent(text);
      } else if (mediaType === "image" || mediaType === "pdf") {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setObjectUrl(url);
      } else {
        const text = await res.text();
        setContent(text);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load file");
    } finally {
      setLoading(false);
    }
  }, [documentId, mediaType]);

  useEffect(() => {
    if (open) loadFile();
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setContent(null);
      setObjectUrl(null);
    };
  }, [open, documentId]);

  const handleDownload = () => {
    const url = documentsApi.fileUrl(documentId);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="relative flex h-[85vh] w-[90vw] max-w-5xl flex-col rounded-xl bg-card shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-3 overflow-hidden">
            <FileIcon type={fileName} className="h-5 w-5 shrink-0 text-muted-foreground" />
            <span className="truncate text-[14px] font-semibold text-ink">{fileName}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="flex h-9 items-center gap-1.5 rounded-lg px-3 text-[13px] font-semibold text-muted-foreground transition-colors hover:bg-canvas-soft hover:text-ink"
            >
              <Download className="h-4 w-4" />
              Download
            </button>
            <button
              onClick={onClose}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-canvas-soft hover:text-ink"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {loading && (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
              <AlertCircle className="h-10 w-10 text-negative" />
              <p className="text-[14px] font-semibold">{error}</p>
              <button
                onClick={loadFile}
                className="rounded-lg bg-canvas-soft px-4 py-2 text-[13px] font-semibold text-ink transition-colors hover:bg-border"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && mediaType === "image" && objectUrl && (
            <div className="flex h-full items-center justify-center">
              <img
                src={objectUrl}
                alt={fileName}
                className="max-h-full max-w-full rounded-lg object-contain"
              />
            </div>
          )}

          {!loading && !error && mediaType === "pdf" && objectUrl && (
            <iframe
              src={objectUrl}
              className="h-full w-full rounded-lg border-0"
              title={fileName}
            />
          )}

          {!loading && !error && mediaType === "text" && content !== null && (
            <pre className="whitespace-pre-wrap break-words rounded-lg bg-canvas-soft p-6 text-[14px] leading-6 text-ink font-mono">
              {content}
            </pre>
          )}

          {!loading && !error && mediaType === "unknown" && content !== null && (
            <pre className="whitespace-pre-wrap break-words rounded-lg bg-canvas-soft p-6 text-[14px] leading-6 text-ink font-mono">
              {content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
