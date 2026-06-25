# MindSync — RAG WhatsApp Bot

WhatsApp bot dengan RAG (Retrieval-Augmented Generation) untuk menjawab pertanyaan dari knowledge base.

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env dengan konfigurasi yang sesuai

# 2. Start services
./mindsync.sh up

# 3. Check status
./mindsync.sh status
```

## API Documentation

Swagger UI: http://localhost:8000/docs

## Project Structure

```
mindsync/
├── backend/
│   ├── app/
│   │   ├── api/          # REST API routes
│   │   ├── core/         # Config, security, dependencies
│   │   ├── rag/          # RAG engine (embedding, retrieval, generation)
│   │   ├── waha/         # WhatsApp HTTP API client
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic (conversation, message handler)
│   │   └── main.py       # FastAPI application
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages (App Router)
│   │   ├── components/   # UI components (shadcn/ui)
│   │   └── lib/          # API client, auth store, query provider
│   └── Dockerfile
├── docker-compose.yml
└── mindsync.sh          # Helper script
```

## Tech Stack

**Backend**
- Python 3.12 + FastAPI
- SQLAlchemy + asyncpg (PostgreSQL)
- Qdrant (vector database)
- multilingual-e5-large (embeddings)
- LiteLLM proxy (LLM generation)

**Frontend**
- Next.js 16 (App Router + TypeScript)
- Tailwind CSS + shadcn/ui
- TanStack Query (data fetching)
- Zustand (auth state)
- Lucide Icons

**Infrastructure**
- Docker Compose
- PostgreSQL 16
- Qdrant
- WAHA (WhatsApp HTTP API)

## Development

```bash
# Start everything
./mindsync.sh up

# Or manually:

# Backend
source .venv/bin/activate
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend
npm run dev
```

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/login` | Admin login page |
| `/dashboard` | Overview stats |
| `/knowledge-base` | Upload & manage documents |
| `/conversations` | View WhatsApp chat history |
| `/sessions` | WhatsApp session management (QR) |
| `/playground` | Test RAG pipeline directly |
| `/settings` | Configure system prompt, model, top_k, threshold |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/login | Admin login (JWT) |
| POST | /api/documents | Upload & ingest document |
| GET | /api/documents | List documents |
| DELETE | /api/documents/{id} | Delete document |
| POST | /api/chat | RAG playground |
| GET | /api/conversations | List conversations |
| GET | /api/conversations/{chat_id}/messages | Get messages |
| POST | /api/sessions/start | Start WAHA session |
| GET | /api/sessions/{name}/qr | Get QR code |
| GET | /api/sessions/{name}/status | Session status |
| GET | /api/settings | Get settings |
| PUT | /api/settings | Update settings |
| GET | /api/stats | Dashboard stats |
| POST | /webhooks/waha | WAHA webhook |
| GET | /health | Health check |

## Status

- [x] Phase 0: Setup & infrastructure
- [x] Phase 1: RAG core pipeline
- [x] Phase 2: WhatsApp ↔ RAG integration
- [x] Phase 3: Frontend admin dashboard (Next.js)
- [ ] Phase 4: Polish & hardening
- [ ] Phase 5: Production deployment

## License

MIT
