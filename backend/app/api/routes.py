"""API routes for the admin dashboard."""

import os
import json
import logging
import mimetypes
from uuid import uuid4
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, async_session_factory
from app.core.security import create_jwt_token
from app.models import User, Document, Conversation, Message, Setting, Category
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
    category_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Upload and ingest a document."""
    # Resolve category (optional)
    category_name: str | None = None
    if category_id:
        cat = await db.scalar(select(Category).where(Category.id == category_id))
        if not cat:
            raise HTTPException(404, "Category not found")
        category_name = cat.name

    # Save document metadata
    doc = Document(
        id=uuid4(),
        name=file.filename or "unknown",
        source=file.filename,
        status="processing",
        category_id=category_id or None,
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
            category=category_name,
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
    category_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List all documents (optionally filtered by category)."""
    stmt = (
        select(Document, Category.name)
        .outerjoin(Category, Document.category_id == Category.id)
        .order_by(Document.created_at.desc())
    )
    if category_id:
        stmt = stmt.where(Document.category_id == category_id)
    result = await db.execute(stmt)
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "source": d.source,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "category_id": str(d.category_id) if d.category_id else None,
            "category_name": cat_name,
        }
        for d, cat_name in result.all()
    ]


# ────────────────────── Categories ──────────────────────


class CategoryRequest(BaseModel):
    name: str


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List document categories."""
    result = await db.execute(select(Category).order_by(Category.name))
    return [{"id": str(c.id), "name": c.name} for c in result.scalars().all()]


@router.post("/categories")
async def create_category(
    req: CategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Create a new category."""
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "Category name required")
    existing = await db.scalar(select(Category).where(Category.name == name))
    if existing:
        raise HTTPException(409, "Category already exists")
    cat = Category(id=uuid4(), name=name)
    db.add(cat)
    await db.commit()
    return {"id": str(cat.id), "name": cat.name}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete a category. Documents keep their data but lose the category link."""
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise HTTPException(404, "Category not found")
    # Unlink documents so the FK doesn't block deletion
    await db.execute(
        Document.__table__.update()
        .where(Document.category_id == category_id)
        .values(category_id=None)
    )
    await db.delete(cat)
    await db.commit()
    return {"status": "deleted", "id": category_id}


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


# ────────────────────── Evaluation ──────────────────────

# Bot phrases indicating it had no answer (mirror message_handler.no_info_phrases)
NO_INFO_PHRASES = [
    "tidak memiliki informasi",
    "tidak ada informasi",
    "belum ada info",
    "tidak tahu",
    "tidak menemukan",
]


@router.get("/evaluation/top-questions")
async def top_questions(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Most frequently asked student questions."""
    from sqlalchemy import func

    stmt = (
        select(Message.content, func.count().label("count"))
        .where(Message.role == "user")
        .group_by(Message.content)
        .order_by(func.count().desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [{"question": content, "count": count} for content, count in result.all()]


@router.get("/evaluation/unanswered")
async def unanswered_questions(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Questions the bot answered with a 'not found' response — KB gaps to fill."""
    from sqlalchemy import or_

    # Assistant messages that look like a no-info response
    stmt = (
        select(Message)
        .where(
            Message.role == "assistant",
            or_(*[Message.content.ilike(f"%{p}%") for p in NO_INFO_PHRASES]),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    no_info_msgs = (await db.execute(stmt)).scalars().all()

    # Pair each with the preceding user question in the same conversation
    out = []
    for m in no_info_msgs:
        prev = await db.scalar(
            select(Message)
            .where(
                Message.conversation_id == m.conversation_id,
                Message.role == "user",
                Message.created_at <= m.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        if prev:
            out.append(
                {
                    "question": prev.content,
                    "answered_at": m.created_at.isoformat() if m.created_at else None,
                }
            )
    return out
