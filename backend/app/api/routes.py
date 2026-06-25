"""API routes for the admin dashboard."""

import os
import json
import logging
import mimetypes
from uuid import uuid4
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, async_session_factory
from app.core.security import create_jwt_token
from app.models import User, Document, Conversation, Message, Setting
from app.rag.engine import RagEngine
from app.rag.ingestion import ingest_document
from app.services.conversation import (
    get_or_create_conversation,
    save_message,
    get_history,
    get_playground_sessions,
    create_playground_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
rag = RagEngine()

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage/documents"))


# ────────────────────── Auth ──────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login admin user — simple JWT."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(401, "Invalid credentials")

    # Simple password check (in production, use proper hashing)
    import hashlib
    if user.password_hash != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid credentials")

    token = create_jwt_token(user.email)
    return {"access_token": token, "token_type": "bearer"}


# ────────────────────── Documents ──────────────────────


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Upload and ingest a document."""
    # Save document metadata
    doc = Document(
        id=uuid4(),
        name=file.filename or "unknown",
        source=file.filename,
        status="processing",
    )
    db.add(doc)
    await db.commit()

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception:
        doc.status = "failed"
        await db.commit()
        raise HTTPException(422, "Failed to read uploaded file")

    # Store original file on disk
    doc_dir = STORAGE_DIR / str(doc.id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / (file.filename or "document")
    file_path.write_bytes(file_bytes)

    # Ingest into vector store
    try:
        chunk_count = await ingest_document(
            rag=rag,
            file_name=file.filename or "unknown",
            file_bytes=file_bytes,
            document_id=str(doc.id),
            source=file.filename,
        )
        doc.status = "done"
        doc.chunk_count = chunk_count
        await db.commit()
        return {"id": str(doc.id), "name": doc.name, "status": "done", "chunks": chunk_count}
    except Exception as e:
        doc.status = "failed"
        await db.commit()
        raise HTTPException(422, str(e))


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List all documents."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "source": d.source,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/documents/{doc_id}/file")
async def preview_document(
    doc_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: str | None = Depends(lambda: None),  # optional auth
):
    """Preview/download the original uploaded file."""
    # Validate token manually if provided as query param
    if not current_user:
        from app.core.security import decode_jwt_token
        if token:
            payload = decode_jwt_token(token)
            if not payload:
                raise HTTPException(401, "Invalid or expired token")
        else:
            raise HTTPException(401, "Missing authentication")

    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    doc_dir = STORAGE_DIR / doc_id
    if not doc_dir.exists():
        raise HTTPException(404, "File not found on disk. Document was uploaded before file storage was enabled. Please re-upload the document.")

    # Find the file in the storage directory
    files = list(doc_dir.iterdir())
    if not files:
        raise HTTPException(404, "File not found on disk")

    file_path = files[0]
    media_type = mimetypes.guess_type(doc.name)[0] or "application/octet-stream"

    return FileResponse(
        path=file_path,
        filename=doc.name,
        media_type=media_type,
    )


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete a document and its vectors."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete vectors from Qdrant using proper Filter object
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        rag.qdrant.delete(
            collection_name="knowledge_base",
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            ),
        )
    except Exception as e:
        logger.warning(f"Failed to delete vectors for document {doc_id}: {e}")

    # Delete stored file
    import shutil
    doc_dir = STORAGE_DIR / doc_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "id": doc_id}


@router.post("/documents/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Re-index a document (placeholder — requires original file)."""
    raise HTTPException(501, "Reindex not yet implemented — store original file for this feature.")


# ────────────────────── Conversations ──────────────────────


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List WhatsApp conversations."""
    from app.services.conversation import get_conversations
    convs = await get_conversations(db, limit=limit, offset=offset, conv_type="whatsapp")
    return [
        {
            "id": str(c.id),
            "chat_id": c.chat_id,
            "contact_name": c.contact_name,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        }
        for c in convs
    ]


@router.get("/conversations/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Get messages for a conversation."""
    result = await db.execute(
        select(Conversation).where(Conversation.chat_id == chat_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


# ────────────────────── Playground (per-admin sessions) ──────────────────────


class ChatRequest(BaseModel):
    query: str
    include_sources: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list = []


async def _resolve_user_id(db: AsyncSession, email: str) -> str:
    """Resolve current user email to user_id (UUID string)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return str(user.id)


async def _get_session_for_user(
    db: AsyncSession, session_id: str, user_id: str
) -> Conversation:
    """Fetch a playground session, verifying ownership."""
    from uuid import UUID
    result = await db.execute(
        select(Conversation).where(Conversation.id == UUID(session_id))
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.type != "playground" or str(conv.user_id) != user_id:
        raise HTTPException(404, "Session not found")
    return conv


@router.get("/playground/sessions")
async def list_playground_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List playground sessions for the current admin."""
    user_id = await _resolve_user_id(db, current_user)
    sessions = await get_playground_sessions(db, user_id)
    return [
        {
            "id": str(s.id),
            "title": s.contact_name or "New Chat",
            "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


class CreateSessionRequest(BaseModel):
    title: str | None = "New Chat"


@router.post("/playground/sessions")
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Create a new playground session."""
    user_id = await _resolve_user_id(db, current_user)
    conv = await create_playground_session(db, user_id, req.title or "New Chat")
    return {
        "id": str(conv.id),
        "title": conv.contact_name,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@router.delete("/playground/sessions/{session_id}")
async def delete_playground_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete a playground session and its messages."""
    user_id = await _resolve_user_id(db, current_user)
    conv = await _get_session_for_user(db, session_id, user_id)
    # Delete messages first (no cascade configured)
    await db.execute(sa_delete(Message).where(Message.conversation_id == conv.id))
    await db.delete(conv)
    await db.commit()
    return {"status": "deleted", "id": session_id}


@router.get("/playground/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Get messages for a playground session."""
    user_id = await _resolve_user_id(db, current_user)
    conv = await _get_session_for_user(db, session_id, user_id)
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/playground/sessions/{session_id}/stream")
async def playground_session_stream(
    session_id: str,
    req: ChatRequest,
    current_user: str = Depends(get_current_user),
):
    """Stream RAG response for a playground session via SSE."""
    # Pre-stream work in isolated session (release before streaming starts)
    async with async_session_factory() as db:
        user_id = await _resolve_user_id(db, current_user)
        conv = await _get_session_for_user(db, session_id, user_id)
        conv_id = conv.id
        history = await get_history(db, conv_id, max_turns=6)
        await save_message(db, conv_id, "user", req.query)

        # Auto-title from first user message if still default
        if conv.contact_name in (None, "", "New Chat"):
            words = req.query.strip().split()
            title = " ".join(words[:8])
            if len(words) > 8:
                title += "…"
            conv.contact_name = title or "New Chat"
            await db.commit()

    async def event_generator():
        accumulated = ""
        try:
            results = await rag.search(req.query)

            if req.include_sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': results})}\n\n"

            context = "\n\n".join(
                f"[Source: {r['source'] or 'unknown'}] {r['text']}"
                for r in results
            )

            async for token in rag.generate_answer_stream(req.query, context, history=history):
                accumulated += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            if accumulated:
                async with async_session_factory() as save_db:
                    await save_message(save_db, conv_id, "assistant", accumulated)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ────────────────────── Sessions ──────────────────────


@router.post("/sessions/start")
async def start_session():
    """Start WAHA WhatsApp session."""
    from app.waha.client import WahaClient
    client = WahaClient()
    return await client.start_session()


@router.post("/sessions/stop")
async def stop_session():
    """Stop WAHA WhatsApp session."""
    from app.waha.client import WahaClient
    client = WahaClient()
    return await client.stop_session()


@router.post("/sessions/restart")
async def restart_session():
    """Restart WAHA WhatsApp session."""
    from app.waha.client import WahaClient
    client = WahaClient()
    return await client.restart_session()


@router.post("/sessions/logout")
async def logout_session():
    """Log out WAHA WhatsApp session (disconnect device)."""
    from app.waha.client import WahaClient
    client = WahaClient()
    return await client.logout_session()


@router.get("/sessions/{name}/qr")
async def get_qr(name: str):
    """Get WAHA session QR code."""
    from app.waha.client import WahaClient
    client = WahaClient()
    qr = await client.get_session_qr(name)
    return {"qr": qr}


@router.get("/sessions/{name}/status")
async def session_status(name: str):
    """Get WAHA session status."""
    from app.waha.client import WahaClient
    client = WahaClient()
    return await client.get_session_status(name)


# ────────────────────── Settings ──────────────────────


@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Get all settings."""
    result = await db.execute(select(Setting))
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}


class SettingsUpdate(BaseModel):
    key: str
    value: str


@router.put("/settings")
async def update_settings(
    req: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Update a setting."""
    result = await db.execute(select(Setting).where(Setting.key == req.key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = req.value
    else:
        setting = Setting(key=req.key, value=req.value)
        db.add(setting)
    await db.commit()
    return {"status": "updated", "key": req.key}


# ────────────────────── Stats ──────────────────────


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Dashboard statistics."""
    from sqlalchemy import func

    msg_count = await db.scalar(select(func.count()).select_from(Message))
    conv_count = await db.scalar(select(func.count()).select_from(Conversation))
    doc_count = await db.scalar(select(func.count()).select_from(Document))

    return {
        "total_messages": msg_count or 0,
        "total_conversations": conv_count or 0,
        "total_documents": doc_count or 0,
    }
