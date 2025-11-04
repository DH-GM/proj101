# db_seed.py
from .db_models import (
    create_db,
    get_session,
    User,
    Post,
    Follow,
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
)
import random, datetime as dt


def seed():
    create_db()
    db = get_session()

    # Users
    handles = ["yourname", "alice", "bob", "charlie", "dana", "eve", "frank"]
    users = {}
    for h in handles:
        u = User(handle=h, display_name=h.capitalize(), bio=f"{h} on social.vim")
        db.add(u)
        users[h] = u
    db.commit()

    # Follows: yourname follows all
    for h in handles[1:]:
        db.add(Follow(follower_id=users["yourname"].id, followed_id=users[h].id))
    db.commit()

    # Posts (top-level)
    texts = [
        "Just shipped a new feature! The TUI is looking amazing 🚀",
        "Working on a new CLI tool for developers. Any testers?",
        "Refactoring is like cleaning your room.",
        "TUIs are underrated. Fight me.",
        "DubHacks prep going well!",
    ]
    posts = []
    for i, t in enumerate(texts):
        author = users[handles[(i % len(handles))]]
        p = Post(
            author_id=author.id,
            content=t,
            created_at=dt.datetime.utcnow() - dt.timedelta(minutes=15 * i),
        )
        db.add(p)
        posts.append(p)
    db.commit()

    # A reply thread to posts[0]
    reply = Post(
        author_id=users["alice"].id,
        content="Looks great! What lib?",
        parent_id=posts[0].id,
    )
    db.add(reply)
    posts[0].comments_count += 1
    db.commit()

    # DMs: conversation yourname <-> alice
    conv = Conversation()
    db.add(conv)
    db.commit()
    db.add_all(
        [
            ConversationParticipant(
                conversation_id=conv.id, user_id=users["yourname"].id
            ),
            ConversationParticipant(conversation_id=conv.id, user_id=users["alice"].id),
        ]
    )
    db.commit()

    db.add_all(
        [
            Message(
                conversation_id=conv.id,
                sender_id=users["alice"].id,
                content="Hey! Did you see the new feature I pushed?",
            ),
            Message(
                conversation_id=conv.id,
                sender_id=users["yourname"].id,
                content="Yes! It looks amazing! 🎉",
            ),
        ]
    )
    db.commit()

    # Notifications for yourname
    db.add_all(
        [
            Notification(
                user_id=users["yourname"].id,
                type="like",
                actor_id=users["bob"].id,
                content=posts[0].content,
                related_post_id=posts[0].id,
            ),
            Notification(
                user_id=users["yourname"].id,
                type="mention",
                actor_id=users["charlie"].id,
                content="@yourname what do you think?",
                related_post_id=posts[1].id,
            ),
        ]
    )
    db.commit()

    print("✅ Seed complete.")


if __name__ == "__main__":
    seed()
