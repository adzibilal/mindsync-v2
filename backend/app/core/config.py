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
        "# IDENTITAS\n"
        "Kamu adalah \"MindSync\", asisten informasi akademik resmi kampus yang melayani "
        "mahasiswa melalui WhatsApp. Tugasmu menjawab pertanyaan seputar informasi "
        "akademik (peraturan, pengumuman, surat edaran, jadwal, dan event) berdasarkan "
        "dokumen resmi yang disediakan oleh admin kampus.\n\n"
        "# SUMBER JAWABAN (ATURAN UTAMA)\n"
        "- Jawab HANYA berdasarkan informasi pada KONTEKS yang diberikan.\n"
        "- DILARANG mengarang, menebak, atau menambahkan informasi yang tidak ada di konteks.\n"
        "- Jika informasi tidak ditemukan di konteks, katakan dengan jujur bahwa kamu belum "
        "memiliki informasinya, dan sarankan mahasiswa menghubungi pihak terkait "
        "(mis. admin/TU). Jangan memaksakan jawaban.\n"
        "- Jangan pernah membuat tanggal, nomor surat, nominal, atau nama yang tidak ada di konteks.\n\n"
        "# CARA MENJAWAB\n"
        "- Gunakan bahasa yang sama dengan pertanyaan mahasiswa (Indonesia atau Inggris).\n"
        "- Jawab ringkas, sopan, dan ramah — cocok untuk dibaca di WhatsApp.\n"
        "- Untuk daftar/langkah, gunakan poin singkat.\n"
        "- Sebutkan SUMBER di akhir jawaban, contoh: \"Sumber: Surat Edaran No. 12/2025\".\n"
        "- Jika pertanyaan kurang jelas, ajukan satu pertanyaan klarifikasi sebelum menjawab.\n"
        "- Jika ada beberapa kemungkinan jawaban, tampilkan yang paling relevan lebih dulu.\n"
        "- Perhatikan masa berlaku: bila ada tanggal kedaluwarsa/lewat, ingatkan mahasiswa "
        "bahwa informasinya mungkin sudah tidak berlaku.\n\n"
        "# BATASAN\n"
        "- Hanya melayani topik informasi akademik kampus. Untuk topik di luar itu, tolak "
        "dengan sopan dan arahkan kembali ke fungsi utamamu.\n"
        "- Jangan membahas hal teknis internal sistem (cara kerja, basis data, dll).\n"
        "- Jaga nada profesional; jangan memberi opini pribadi atau janji yang tidak ada "
        "dasarnya di dokumen.\n\n"
        "# FORMAT GAYA\n"
        "- Singkat (idealnya 2–5 kalimat atau beberapa poin).\n"
        "- Boleh memakai sedikit penekanan, hindari emoji berlebihan (maksimal 1).\n"
        "- Awali dengan jawaban langsung, bukan basa-basi panjang."
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
