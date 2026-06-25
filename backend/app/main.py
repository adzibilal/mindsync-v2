"""MindSync — FastAPI application entry point."""

import logging
import json
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import engine
from app.models import Base
from app.waha.webhook import router as webhook_router
from app.api.routes import router as api_router


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    """Setup structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # Remove default handlers
    for h in root.handlers[:-1]:
        root.removeHandler(h)


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    settings = get_settings()
    logger.info("🚀 Starting MindSync Backend")
    logger.info(f"   Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
    logger.info(f"   Qdrant: {settings.qdrant_url}")
    logger.info(f"   WAHA: {settings.waha_url}")

    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Mini-migration: create_all won't add new columns to existing tables.
        await conn.exec_driver_sql(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES categories(id)"
        )
    logger.info("✅ Database tables ready")

    # Create Qdrant collection (sync, uses config dim, no embedding needed)
    try:
        from app.rag.engine import RagEngine
        rag = RagEngine()
        rag.ensure_collection()
        logger.info(f"✅ Qdrant collection ready (dim={settings.embedding_dim})")
    except Exception as e:
        logger.warning(f"Qdrant collection not ready: {e}")

    logger.info(f"   Chat model: {settings.litellm_model}")
    logger.info(f"   Embedding: {settings.embedding_model} (dim={settings.embedding_dim})")

    yield

    await engine.dispose()
    logger.info("👋 MindSync Backend stopped")


app = FastAPI(
    title="MindSync",
    description="RAG WhatsApp Bot Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhook_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mindsync"}
