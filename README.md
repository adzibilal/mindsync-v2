# MindSync — Asisten Informasi Akademik (RAG WhatsApp Bot)

Sistem informasi akademik berbasis percakapan. Admin kampus mengunggah dokumen
resmi (peraturan, pengumuman, surat edaran, jadwal, event); mahasiswa bertanya
lewat **WhatsApp** dan menerima jawaban ringkas yang **bersumber dari dokumen
resmi** via pipeline RAG (Retrieval-Augmented Generation).

## Fitur

- 📄 **Knowledge base** — upload PDF, DOCX, TXT, MD, dan **gambar hasil pindai (OCR)**.
- 🗂️ **Kategori dokumen** dinamis (dikelola admin) + filter.
- 💬 **WhatsApp Q&A** via WAHA — debounce, indikator "diketik", rate limit.
- 🔎 **Sumber jawaban** dikutip oleh model pada tiap balasan.
- 🙅 **Jawaban jujur "tidak ditemukan"** saat info tak ada di knowledge base.
- 📊 **Evaluasi** — pertanyaan terbanyak & pertanyaan yang belum terjawab (bahan perbaikan KB).
- 🧪 **Playground** — uji RAG langsung dari dashboard (streaming + lihat sumber).
- ⚙️ **System prompt** dapat diedit admin (tersimpan di DB, langsung dipakai).

## Arsitektur

```
Mahasiswa (WhatsApp) ──> WAHA (VPS) ──webhook──> Backend (FastAPI)
                                                     │
                          ┌──────────────┬───────────┼───────────────┐
                       Postgres        Qdrant     LiteLLM router   (OCR Tesseract)
                      (metadata)    (vektor KB)   (LLM+embedding)
                                                     │
Admin (Browser) ──> Frontend (Next.js) ──REST──> Backend
```

- **WAHA self-hosted** (di VPS, mis. `https://waha.adzibilal.my.id`) — tidak lagi di docker-compose.
- Karena WAHA remote, backend harus dijangkau publik (saat dev pakai Cloudflare Tunnel/ngrok → set `WEBHOOK_URL`).

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env        # isi WAHA_URL, WAHA_API_KEY, WEBHOOK_URL, LITELLM_*, dll

# 2. (sekali) install OCR engine untuk dokumen gambar
sudo apt-get install -y tesseract-ocr tesseract-ocr-ind

# 3. Jalankan semua (Docker: Postgres+Qdrant, lalu Backend & Frontend)
./mindsync.sh up

# 4. Cek status
./mindsync.sh status
```

`./mindsync.sh {up|down|logs|logs-be|logs-fe|status}`

- API docs (Swagger): http://localhost:8000/docs
- Dashboard: http://localhost:3000

> Catatan dev: backend dijalankan tanpa `--reload` oleh `mindsync.sh`, jadi
> restart setelah ubah kode Python. URL tunnel ganti tiap restart → perbarui
> `WEBHOOK_URL` lalu `POST /api/sessions/start` (webhook WAHA otomatis diperbarui).

## Konfigurasi (.env)

| Var | Keterangan |
|-----|------------|
| `DATABASE_URL` | Postgres (async) |
| `QDRANT_URL` | Vector DB |
| `WAHA_URL`, `WAHA_API_KEY` | Instance WAHA self-hosted di VPS |
| `WAHA_HMAC_KEY` | Secret verifikasi webhook (SHA-512) |
| `WEBHOOK_URL` | URL publik backend (tunnel saat dev) untuk webhook WAHA |
| `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL` | Router LLM (OpenAI-compatible) |
| `EMBEDDING_API_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | API embedding (default `text-embedding-3-large`, dim 3072) |
| `JWT_SECRET` | Token login admin |

## Struktur Project

```
mindsync/
├── backend/
│   ├── app/
│   │   ├── api/routes.py    # REST API (auth, documents, categories, evaluation, sessions, settings)
│   │   ├── core/            # config, security (JWT+HMAC), deps
│   │   ├── rag/             # engine (embed/retrieve/generate) + ingestion (extract+OCR+chunk)
│   │   ├── waha/            # client + webhook handler
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # conversation, message_handler, rate_limiter
│   │   └── main.py          # FastAPI app + mini-migrasi startup
│   ├── pyproject.toml
│   └── Dockerfile           # termasuk tesseract-ocr (OCR)
├── frontend/
│   └── src/
│       ├── app/(auth)/login, app/(dashboard)/{dashboard,knowledge-base,conversations,
│       │                       evaluation,sessions,playground,settings}
│       ├── components/{app,ui}
│       └── lib/             # api client, auth store, query provider
├── docker-compose.yml       # Postgres + Qdrant (WAHA = VPS terpisah)
└── mindsync.sh
```

## Model Data

**PostgreSQL** — `users`, `categories`, `documents` (FK→users, categories),
`conversations` (whatsapp/playground), `messages` (FK→conversations),
`settings` (key-value, mis. `system_prompt`).

**Qdrant** — koleksi `knowledge_base`; tiap chunk = 1 point, vektor 3072-dim,
payload `{document_id, source, chunk_index, category, text}`. `documents.id`
(Postgres) ⇄ `payload.document_id` (Qdrant).

## Tech Stack

**Backend** — Python 3.12, FastAPI, SQLAlchemy + asyncpg (PostgreSQL 16),
Qdrant, LiteLLM router (LLM + embedding `text-embedding-3-large`),
PyMuPDF/python-docx/Tesseract (ekstraksi & OCR), PyJWT.

**Frontend** — Next.js (App Router, TypeScript), Tailwind CSS + shadcn/ui,
TanStack Query, Zustand (auth), Lucide Icons.

**Infra** — Docker Compose (Postgres, Qdrant), WAHA self-hosted (VPS).

## Frontend Pages

| Route | Deskripsi |
|-------|-----------|
| `/login` | Login admin |
| `/dashboard` | Statistik ringkas |
| `/knowledge-base` | Upload & kelola dokumen + kategori |
| `/conversations` | Riwayat chat WhatsApp |
| `/evaluation` | Pertanyaan terbanyak & belum terjawab |
| `/sessions` | Kelola sesi WhatsApp (QR, start/stop/restart/logout) |
| `/playground` | Uji RAG langsung |
| `/settings` | Edit system prompt |

## API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/auth/login` | Login admin (JWT) |
| GET/POST | `/api/documents` | List (filter `?category_id=`) / upload+ingest |
| DELETE | `/api/documents/{id}` | Hapus dokumen + vektornya |
| GET | `/api/documents/{id}/file` | Preview file asli |
| GET/POST | `/api/categories` | List / buat kategori |
| DELETE | `/api/categories/{id}` | Hapus kategori |
| GET | `/api/conversations` | List percakapan |
| GET | `/api/conversations/{chat_id}/messages` | Pesan per percakapan |
| GET | `/api/evaluation/top-questions` | Pertanyaan terbanyak |
| GET | `/api/evaluation/unanswered` | Pertanyaan dijawab "tidak ditemukan" |
| GET/POST/DELETE | `/api/playground/sessions...` | Sesi playground (CRUD) |
| POST | `/api/playground/sessions/{id}/stream` | Stream RAG (SSE) |
| POST | `/api/sessions/start\|stop\|restart\|logout` | Kelola sesi WAHA |
| GET | `/api/sessions/{name}/status` \| `/qr` | Status / QR sesi |
| GET/PUT | `/api/settings` | Baca / ubah pengaturan (system prompt) |
| GET | `/api/stats` | Statistik dashboard |
| POST | `/webhooks/waha` | Webhook WAHA (verifikasi HMAC SHA-512) |
| GET | `/health` | Health check |

## Status

- [x] Setup & infrastruktur
- [x] RAG core pipeline
- [x] Integrasi WhatsApp ↔ RAG (WAHA self-hosted)
- [x] Dashboard admin (Next.js)
- [x] Penyesuaian skripsi: kategori dokumen, OCR gambar, sumber pada jawaban, view evaluasi
- [ ] Hardening & deployment produksi

## License

MIT
