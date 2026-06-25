"""Message handler service — processes incoming WhatsApp messages with rate limiting, retry, and edge cases."""

import logging
import asyncio
import re
from typing import Dict

from app.core.config import get_settings
from app.core.deps import async_session_factory
from app.rag.engine import RagEngine
from app.services.conversation import (
    get_or_create_conversation,
    save_message,
    get_history,
)
from app.services.rate_limiter import rate_limiter
from app.waha.client import WahaClient

logger = logging.getLogger(__name__)
settings = get_settings()
waha_client = WahaClient()
rag = RagEngine()

# Debounce state: chat_id → (pending_text, task)
_debounce_state: Dict[str, dict] = {}

# Regex to detect if text is only emoji/whitespace
_EMOJI_ONLY_RE = re.compile(
    r"^[\s"
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"  # dingbats
    r"\U0001f900-\U0001f9FF"  # supplemental
    r"\U0001FA00-\U0001FA6F"  # chess symbols
    r"\U0001FA70-\U0001FAFF"  # symbols ext
    r"]+$"
)


async def handle_media_message(session: str, chat_id: str, msg_type: str):
    """Handle media messages — reply with text-only notice."""
    type_names = {
        "image": "gambar",
        "video": "video",
        "audio": "audio",
        "ptt": "pesan suara",
        "document": "dokumen",
        "sticker": "stiker",
    }
    type_name = type_names.get(msg_type, "media")

    try:
        await waha_client.send_seen(session, chat_id)
        await waha_client.send_text(
            session,
            chat_id,
            f"Maaf, saat ini saya hanya bisa memproses pesan teks. "
            f"Silakan kirim pertanyaan kamu dalam bentuk teks. 📝",
        )
        logger.info(f"Media message handled for {chat_id}: type={msg_type}")
    except Exception as e:
        logger.error(f"Error handling media from {chat_id}: {e}")


async def _process_message(
    session: str, chat_id: str, text: str, message_id: str | None = None
):
    """Core logic: rate check → save → retrieve → generate → reply."""
    try:
        # Rate limiting check
        if not rate_limiter.is_allowed(chat_id):
            remaining_wait = settings.rate_limit_window
            logger.warning(
                "rate_limit_exceeded",
                extra={"chat_id": chat_id, "remaining": rate_limiter.remaining(chat_id)},
            )
            try:
                await waha_client.send_text(
                    session,
                    chat_id,
                    f"{settings.rate_limit_message}\n(Coba lagi dalam ~{remaining_wait} detik)",
                )
            except Exception:
                pass
            return

        # Edge case: empty or emoji-only message
        if not text.strip() or _EMOJI_ONLY_RE.match(text):
            try:
                await waha_client.send_text(
                    session,
                    chat_id,
                    "Halo! Silakan kirim pertanyaan kamu dalam bentuk teks ya. 😊",
                )
            except Exception:
                pass
            return

        async with async_session_factory() as db:
            # Get or create conversation
            conv = await get_or_create_conversation(db, chat_id)

            # Save user message
            await save_message(db, conv.id, "user", text, message_id)

            # Get conversation history
            history = await get_history(
                db, conv.id, max_turns=settings.default_max_history_turns
            )

        # Send UX indicators
        await waha_client.send_seen(session, chat_id)
        await waha_client.start_typing(session, chat_id)

        # Run RAG pipeline
        result = await rag.answer_query(text, history=history)
        answer = result["answer"]

        # Log if bot said "tidak tahu" (for knowledge base improvement)
        no_info_phrases = [
            "tidak memiliki informasi",
            "tidak ada informasi",
            "belum ada info",
            "tidak tahu",
            "tidak menemukan",
        ]
        if any(phrase in answer.lower() for phrase in no_info_phrases):
            logger.info(
                "no_info_response",
                extra={
                    "chat_id": chat_id,
                    "query": text[:100],
                    "answer": answer[:100],
                },
            )

        # Stop typing + send reply
        await waha_client.stop_typing(session, chat_id)
        await waha_client.send_text(session, chat_id, answer)

        # Save assistant message
        async with async_session_factory() as db:
            conv = await get_or_create_conversation(db, chat_id)
            await save_message(db, conv.id, "assistant", answer)

        logger.info(
            "message_processed",
            extra={
                "chat_id": chat_id,
                "query_length": len(text),
                "answer_length": len(answer),
                "sources_count": len(result.get("sources", [])),
            },
        )

    except Exception as e:
        logger.error(
            "message_processing_error",
            extra={"chat_id": chat_id, "error": str(e)},
            exc_info=True,
        )
        # Try to send error message
        try:
            await waha_client.stop_typing(session, chat_id)
            await waha_client.send_text(
                session,
                chat_id,
                settings.llm_fallback_message,
            )
        except Exception:
            pass


async def handle_message(
    session: str, chat_id: str, text: str, message_id: str | None = None
):
    """
    Handle incoming message with debounce.
    Waits a few seconds and combines rapid messages before processing.
    """
    debounce_sec = settings.debounce_seconds

    # If there's a pending message for this chat, append text and reset timer
    if chat_id in _debounce_state:
        _debounce_state[chat_id]["text"] += f"\n{text}"
        if "task" in _debounce_state[chat_id]:
            _debounce_state[chat_id]["task"].cancel()
    else:
        _debounce_state[chat_id] = {"text": text}

    # Create a task that fires after debounce period
    async def _debounced_process():
        try:
            await asyncio.sleep(debounce_sec)
            combined = _debounce_state.pop(chat_id, {}).get("text", text)
            await _process_message(session, chat_id, combined, message_id)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(_debounced_process())
    _debounce_state[chat_id]["task"] = task
