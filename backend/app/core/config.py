"""Application configuration via environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Look for .env in current dir, then parent (for running from backend/)
_env_file = Path(".env") if Path(".env").exists() else Path("../.env")


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://mindsync:mindsync@localhost:5432/mindsync"

    # Qdrant
    qdrant_url: str = "http://localhost:6334"

    # WAHA
    waha_url: str = "http://localhost:3001"
    waha_api_key: str = ""
    waha_hmac_key: str = ""
    webhook_url: str = ""  # public URL of this backend (tunnel in dev), no trailing slash

    # LiteLLM / Chat Router
    litellm_base_url: str = ""
    litellm_api_key: str = ""
    litellm_model: str = "free-model"

    # Embedding API (via router, not local fastembed)
    embedding_api_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "openrouter/openai/text-embedding-3-large"
    embedding_dim: int = 3072

    # JWT
    jwt_secret: str = "dev-secret-change-me"

    # RAG defaults
    default_top_k: int = 4
    default_threshold: float = 0.2
    default_max_history_turns: int = 6
    default_system_prompt: str = (
        "Kamu adalah asisten AI yang bertugas menjawab pertanyaan pengguna berdasarkan informasi yang tersedia dalam konteks berikut.\n\n"
        "ATURAN PENTING:\n"
        "1. JAWAB HANYA berdasarkan informasi yang ada dalam konteks yang diberikan. Jangan menambahkan informasi dari pengetahuan umum atau asumsi.\n"
        "2. Jika konteks TIDAK mengandung informasi yang cukup untuk menjawab pertanyaan, katakan dengan jujur: \"Maaf, saya tidak memiliki informasi tersebut dalam basis pengetahuan saya.\"\n"
        "3. Jangan pernah mengarang, menebak, atau membuat informasi yang tidak didukung oleh konteks.\n"
        "4. Jika pertanyaan tidak jelas, minta klarifikasi.\n"
        "5. Jawab dalam bahasa yang sama dengan pertanyaan pengguna (Bahasa Indonesia jika pertanyaan dalam Bahasa Indonesia).\n"
        "6. Jawab secara ringkas dan informatif. Gunakan poin-poin jika perlu."
    )

    # Debounce
    debounce_seconds: float = 2.5

    # Rate limiting
    rate_limit_max: int = 10
    rate_limit_window: int = 60  # seconds
    rate_limit_message: str = (
        "Maaf, kamu mengirim terlalu banyak pesan. Silakan tunggu sebentar sebelum mengirim pesan lagi."
    )

    # LLM retry
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0
    llm_timeout: int = 60
    llm_fallback_message: str = (
        "Maaf, layanan AI sedang tidak tersedia. Silakan coba lagi dalam beberapa saat."
    )

    # Max message length
    max_message_length: int = 4000

    model_config = {"env_file": str(_env_file), "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
