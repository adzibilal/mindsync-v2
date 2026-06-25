"""WAHA webhook handler — receives WhatsApp events."""

import json
import logging

from fastapi import APIRouter, Header, Request, BackgroundTasks, HTTPException

from app.core.config import get_settings
from app.core.security import verify_hmac

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/waha")
async def waha_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_hmac: str = Header(None),
):
    """Handle incoming WhatsApp events from WAHA."""
    settings = get_settings()
    raw_body = await request.body()

    # Verify HMAC if configured
    if settings.waha_hmac_key:
        if not verify_hmac(raw_body, x_webhook_hmac, settings.waha_hmac_key):
            logger.warning("Webhook HMAC verification failed")
            raise HTTPException(status_code=403, detail="Invalid HMAC")

    # Parse JSON
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload received")
        return {"status": "error", "message": "Invalid JSON"}

    # Validate required fields
    event_type = event.get("event")
    if not event_type:
        return {"status": "ignored"}

    # Only handle message events
    if event_type != "message":
        return {"status": "ignored"}

    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return {"status": "ignored"}

    # Ignore our own messages
    if payload.get("fromMe", False):
        return {"status": "ignored"}

    session = event.get("session", "default")
    chat_id = payload.get("from", "")
    message_id = payload.get("id", "")

    # Validate chat_id format (should end with @c.us or @g.us)
    if not chat_id or not ("@" in chat_id):
        logger.warning(f"Invalid chat_id format: {chat_id}")
        return {"status": "ignored"}

    # Detect message type
    msg_type = payload.get("type", "chat")
    body = payload.get("body", "").strip()

    # Handle media messages (image, video, audio, document, sticker)
    media_types = {"image", "video", "audio", "ptt", "document", "sticker"}
    if msg_type in media_types:
        logger.info(f"Media message from {chat_id}: type={msg_type}")
        from app.services.message_handler import handle_media_message
        background_tasks.add_task(
            handle_media_message,
            session=session,
            chat_id=chat_id,
            msg_type=msg_type,
        )
        return {"status": "ok"}

    # Text message processing
    text = body

    # Ignore empty messages after stripping
    if not text:
        return {"status": "ignored"}

    # Truncate excessively long messages
    max_len = settings.max_message_length
    if len(text) > max_len:
        text = text[:max_len] + "..."
        logger.warning(f"Message truncated to {max_len} chars from {chat_id}")

    logger.info(
        "webhook_received",
        extra={
            "chat_id": chat_id,
            "msg_type": msg_type,
            "text_length": len(text),
            "message_id": message_id,
        },
    )

    # Process in background to respond quickly to webhook
    from app.services.message_handler import handle_message
    background_tasks.add_task(
        handle_message,
        session=session,
        chat_id=chat_id,
        text=text,
        message_id=message_id,
    )

    return {"status": "ok"}
