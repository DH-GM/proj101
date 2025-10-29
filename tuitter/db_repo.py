# db_repo.py
from typing import List, Optional
from sqlalchemy import select, update, delete
from .db_models import (
    create_db,
    get_session,
    User,
    Post,
    Message,
    Conversation,
    ConversationParticipant,
    Notification,
)
import datetime as dt

# Ensure tables exist
create_db()


# ---------- USERS ----------
def create_user(handle: str, display_name: str, bio: str = "") -> User:
    with get_session() as db:
        u = User(handle=handle, display_name=display_name, bio=bio)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u


def get_user_by_handle(handle: str) -> Optional[User]:
    with get_session() as db:
        return db.execute(
            select(User).where(User.handle == handle)
        ).scalar_one_or_none()


def update_user_bio(user_id: str, new_bio: str) -> bool:
    with get_session() as db:
        rows = db.execute(
            update(User)
            .where(User.id == user_id)
            .values(bio=new_bio, last_seen_at=dt.datetime.utcnow())
        ).rowcount
        db.commit()
        return rows > 0


def delete_user(user_id: str) -> bool:
    with get_session() as db:
        rows = db.execute(delete(User).where(User.id == user_id)).rowcount
        db.commit()
        return rows > 0


# ---------- POSTS ----------
def create_post(author_id: str, content: str, parent_id: Optional[str] = None) -> Post:
    with get_session() as db:
        p = Post(author_id=author_id, content=content, parent_id=parent_id)
        db.add(p)
        if parent_id:
            parent = db.get(Post, parent_id)
            if parent:
                parent.comments_count = (parent.comments_count or 0) + 1
        db.commit()
        db.refresh(p)
        return p


def get_post(post_id: str) -> Optional[Post]:
    with get_session() as db:
        return db.get(Post, post_id)


def list_feed(limit: int = 50) -> List[Post]:
    with get_session() as db:
        return (
            db.execute(select(Post).order_by(Post.created_at.desc()).limit(limit))
            .scalars()
            .all()
        )


def update_post_content(post_id: str, new_content: str) -> bool:
    with get_session() as db:
        rows = db.execute(
            update(Post).where(Post.id == post_id).values(content=new_content)
        ).rowcount
        db.commit()
        return rows > 0


def delete_post(post_id: str) -> bool:
    with get_session() as db:
        post = db.get(Post, post_id)
        if not post:
            return False
        if post.parent_id:
            parent = db.get(Post, post.parent_id)
            if parent and parent.comments_count and parent.comments_count > 0:
                parent.comments_count -= 1
        db.delete(post)
        db.commit()
        return True


# ---------- DMs ----------
def get_or_create_dm(user_a: str, user_b: str) -> Conversation:
    with get_session() as db:
        # find existing conversation containing BOTH users
        candidates = db.query(Conversation).all()
        for c in candidates:
            ids = {
                p.user_id
                for p in db.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == c.id
                )
            }
            if {user_a, user_b}.issubset(ids):
                return c
        c = Conversation()
        db.add(c)
        db.commit()
        db.refresh(c)
        db.add_all(
            [
                ConversationParticipant(conversation_id=c.id, user_id=user_a),
                ConversationParticipant(conversation_id=c.id, user_id=user_b),
            ]
        )
        db.commit()
        return c


def send_dm(conversation_id: str, sender_id: str, text: str) -> Message:
    with get_session() as db:
        m = Message(conversation_id=conversation_id, sender_id=sender_id, content=text)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m


def list_dm(conversation_id: str, limit: int = 100) -> List[Message]:
    with get_session() as db:
        return (
            db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )


def delete_message(message_id: str) -> bool:
    with get_session() as db:
        rows = db.execute(delete(Message).where(Message.id == message_id)).rowcount
        db.commit()
        return rows > 0


# ---------- Notifications ----------
def mark_notification_read(notification_id: str) -> bool:
    with get_session() as db:
        rows = db.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(read=True)
        ).rowcount
        db.commit()
        return rows > 0
