from __future__ import annotations

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.database.models import Document, Message, User


def upsert_user(
    session: Session,
    user_id: int,
    username: str | None,
    full_name: str | None,
) -> User:
    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=username, full_name=full_name)
        session.add(user)
    else:
        user.username = username
        user.full_name = full_name

    session.flush()
    return user


def create_document(
    session: Session,
    user_id: int,
    source_name: str | None,
    source_type: str,
    text_length: int,
    chunks_count: int,
) -> Document:
    document = Document(
        user_id=user_id,
        source_name=source_name,
        source_type=source_type,
        text_length=text_length,
        chunks_count=chunks_count,
    )
    session.add(document)
    session.flush()
    return document


def create_message(session: Session, user_id: int, role: str, text: str) -> Message:
    message = Message(user_id=user_id, role=role, text=text)
    session.add(message)
    session.flush()
    return message


def clear_user_knowledge(session: Session, user_id: int) -> None:
    session.execute(delete(Document).where(Document.user_id == user_id))
    session.execute(delete(Message).where(Message.user_id == user_id))


def user_has_knowledge(session: Session, user_id: int) -> bool:
    statement = select(func.count(Document.id)).where(Document.user_id == user_id)
    return bool(session.scalar(statement) or 0)


def get_user_document_count(session: Session, user_id: int) -> int:
    statement = select(func.count(Document.id)).where(Document.user_id == user_id)
    return int(session.scalar(statement) or 0)


def get_last_document(session: Session, user_id: int) -> Document | None:
    statement = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(desc(Document.created_at), desc(Document.id))
        .limit(1)
    )
    return session.scalar(statement)
