"""Conversation memory service — manages chat history in PostgreSQL."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


async def get_or_create_conversation(
    db: AsyncSession,
    chat_id: str,
    contact_name: str | None = None,
    conv_type: str = "whatsapp",
    user_id: str | None = None,
) -> Conversation:
    """Get existing conversation or create new one."""
    result = await db.execute(
        select(Conversation).where(Conversation.chat_id == chat_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        conv = Conversation(
            id=uuid4(),
            chat_id=chat_id,
            contact_name=contact_name or chat_id,
            type=conv_type,
            user_id=user_id,
        )
        db.add(conv)
        await db.commit()
    return conv


async def save_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    waha_message_id: str | None = None,
) -> Message:
    """Save a message to DB."""
    msg = Message(
        id=uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        waha_message_id=waha_message_id,
    )
    db.add(msg)

    # Update conversation timestamp
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.last_message_at = datetime.utcnow()

    await db.commit()
    return msg


async def get_history(
    db: AsyncSession, conversation_id: str, max_turns: int = 6
) -> list[dict]:
    """Get last N turns of conversation history."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(max_turns * 2)  # user + assistant per turn
    )
    messages = result.scalars().all()
    # Reverse to chronological order
    return [
        {"role": m.role, "content": m.content}
        for m in reversed(messages)
    ]


async def get_conversations(
    db: AsyncSession, limit: int = 50, offset: int = 0, conv_type: str = "whatsapp"
) -> list[Conversation]:
    """List conversations by type, recent first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.type == conv_type)
        .order_by(desc(Conversation.last_message_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_playground_sessions(
    db: AsyncSession, user_id: str, limit: int = 50
) -> list[Conversation]:
    """List playground sessions for a specific user."""
    from uuid import UUID
    result = await db.execute(
        select(Conversation)
        .where(Conversation.type == "playground", Conversation.user_id == UUID(user_id))
        .order_by(desc(Conversation.last_message_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_playground_session(
    db: AsyncSession, user_id: str, title: str = "New Chat"
) -> Conversation:
    """Create a new playground session for a user."""
    from uuid import UUID
    session_id = uuid4()
    conv = Conversation(
        id=session_id,
        chat_id=f"playground:{user_id}:{session_id}",
        contact_name=title,
        type="playground",
        user_id=UUID(user_id),
    )
    db.add(conv)
    await db.commit()
    return conv
