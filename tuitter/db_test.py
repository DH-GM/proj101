# db_test.py
from .db_models import get_session, User, Post, Message, Notification, Follow

db = get_session()

users = db.query(User).all()
posts = db.query(Post).order_by(Post.created_at.desc()).all()
follows = db.query(Follow).count()
notifs = db.query(Notification).count()
msgs = db.query(Message).count()

print(f"Users: {len(users)}")
print(
    f"Posts: {len(posts)} (latest='{posts[0].content}' by author_id={posts[0].author_id})"
)
print(f"Follows: {follows}")
print(f"Notifications: {notifs}")
print(f"Messages: {msgs}")
