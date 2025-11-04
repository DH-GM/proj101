from .db_models import get_session, User
from .db_repo import (
    create_user,
    update_user_bio,
    delete_user,
    create_post,
    update_post_content,
    delete_post,
    list_feed,
)

# create user
u = create_user("mohamed", "Mohamed")
print("User:", u.id, u.handle)

# update user
ok = update_user_bio(u.id, "CS student at WSU")
print("Updated bio:", ok)

# create a post
p = create_post(u.id, "Hello from CRUD!")
print("Post:", p.id, p.content)

# update post
ok = update_post_content(p.id, "Edited: Hello from CRUD!")
print("Updated post:", ok)

# read feed
feed = list_feed(5)
print("Feed count:", len(feed))

# delete post
print("Deleted post:", delete_post(p.id))

# delete user (will fail if user still has posts/refs—do after deleting their data)
print("Deleted user:", delete_user(u.id))
