"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { documentsApi, categoriesApi } from "@/lib/api";
import { Upload, Trash2, BookOpen, Eye, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { FilePreview } from "@/components/app/file-preview";

export default function KnowledgeBasePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<{ id: string; name: string } | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>(""); // "" = all
  const [uploadCategory, setUploadCategory] = useState<string>(""); // "" = uncategorized

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: categoriesApi.list,
  });

  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents", filterCategory],
    queryFn: () => documentsApi.list(filterCategory || undefined),
  });

  const uploadMutation = useMutation({
    mutationFn: documentsApi.upload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      toast.success("Document uploaded");
    },
    onError: (err: Error) => toast.error(`Upload failed: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: documentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setDeleteId(null);
      toast.success("Document deleted");
    },
    onError: (err: Error) => toast.error(`Delete failed: ${err.message}`),
  });

  const createCategoryMutation = useMutation({
    mutationFn: categoriesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("Kategori ditambahkan");
    },
    onError: (err: Error) => toast.error(`Gagal: ${err.message}`),
  });

  const deleteCategoryMutation = useMutation({
    mutationFn: categoriesApi.delete,
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      if (filterCategory === id) setFilterCategory("");
      toast.success("Kategori dihapus");
    },
    onError: (err: Error) => toast.error(`Gagal: ${err.message}`),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    uploadMutation.mutate({ file, categoryId: uploadCategory || undefined });
    e.target.value = "";
  };

  const handleAddCategory = () => {
    const name = window.prompt("Nama kategori baru (mis. Surat Edaran):");
    if (name?.trim()) createCategoryMutation.mutate(name.trim());
  };

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-[40px] font-[900] leading-tight tracking-tight text-ink">
            Knowledge Base
          </h1>
          <p className="mt-1 text-[16px] font-semibold text-muted-foreground">
            Manage documents for RAG retrieval
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={uploadCategory}
            onChange={(e) => setUploadCategory(e.target.value)}
            className="rounded-xl border border-border bg-card px-3 py-2.5 text-[14px] font-semibold text-ink"
            title="Kategori untuk dokumen yang diupload"
          >
            <option value="">Tanpa kategori</option>
            {categories?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-[14px] font-semibold text-primary-foreground transition-all hover:bg-primary-active active:bg-primary-neutral disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? "Uploading..." : "Upload Document"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.svg,.webp"
            onChange={handleFileChange}
          />
        </div>
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setFilterCategory("")}
          className={`rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors ${
            filterCategory === ""
              ? "bg-primary text-primary-foreground"
              : "bg-canvas-soft text-ink hover:bg-border"
          }`}
        >
          Semua
        </button>
        {categories?.map((c) => (
          <span
            key={c.id}
            className={`group inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors ${
              filterCategory === c.id
                ? "bg-primary text-primary-foreground"
                : "bg-canvas-soft text-ink hover:bg-border"
            }`}
          >
            <button onClick={() => setFilterCategory(c.id)}>{c.name}</button>
            <button
              onClick={() => {
                if (confirm(`Hapus kategori "${c.name}"? Dokumen tetap ada, hanya kehilangan label.`)) {
                  deleteCategoryMutation.mutate(c.id);
                }
              }}
              className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-negative"
              title="Hapus kategori"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <button
          onClick={handleAddCategory}
          className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-3 py-1.5 text-[13px] font-semibold text-muted-foreground transition-colors hover:bg-canvas-soft hover:text-ink"
        >
          <Plus className="h-3.5 w-3.5" /> Kategori
        </button>
      </div>

      <div className="rounded-xl bg-card p-6">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-[16px] bg-canvas-soft" />
            ))}
          </div>
        ) : documents && documents.length > 0 ? (
          <div className="space-y-0">
            {documents.map((doc, i) => (
              <div
                key={doc.id}
                className={`flex items-center justify-between py-4 ${
                  i > 0 ? "border-t border-border" : ""
                }`}
              >
                <button
                  onClick={() => setPreviewDoc({ id: doc.id, name: doc.name })}
                  className="flex items-center gap-3 text-left transition-opacity hover:opacity-70"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-canvas-soft">
                    <BookOpen className="h-5 w-5 text-ink" />
                  </div>
                  <div>
                    <p className="text-[14px] font-semibold text-ink">{doc.name}</p>
                    <p className="text-[12px] text-muted-foreground">
                      {doc.chunk_count} chunks
                      {doc.created_at && ` · ${new Date(doc.created_at).toLocaleDateString()}`}
                    </p>
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  {doc.category_name && (
                    <span className="rounded-full bg-canvas-soft px-3 py-1 text-[12px] font-semibold text-ink">
                      {doc.category_name}
                    </span>
                  )}
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
                  <button
                    onClick={() => setPreviewDoc({ id: doc.id, name: doc.name })}
                    className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-canvas-soft hover:text-ink"
                    title="Preview file"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setDeleteId(doc.id)}
                    className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-canvas-soft hover:text-negative"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-canvas-soft">
              <BookOpen className="h-6 w-6 text-muted-foreground" />
            </div>
            <p className="mt-4 text-[14px] text-muted-foreground">
              No documents yet. Upload a PDF, DOCX, TXT, MD, or scanned image to get started.
            </p>
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="w-full max-w-sm rounded-xl bg-card p-8">
            <h3 className="font-heading text-[20px] font-[900] text-ink">Delete Document</h3>
            <p className="mt-2 text-[14px] text-muted-foreground">
              This will remove the document and all its vector chunks from the knowledge base.
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setDeleteId(null)}
                className="flex-1 rounded-xl bg-canvas-soft px-5 py-2.5 text-[14px] font-semibold text-ink transition-all hover:bg-border"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteId)}
                disabled={deleteMutation.isPending}
                className="flex-1 rounded-xl bg-negative px-5 py-2.5 text-[14px] font-semibold text-white transition-all hover:bg-negative-deep disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File preview */}
      {previewDoc && (
        <FilePreview
          documentId={previewDoc.id}
          fileName={previewDoc.name}
          open={!!previewDoc}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </div>
  );
}
