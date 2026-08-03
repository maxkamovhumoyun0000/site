import re

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'r') as f:
    content = f.read()

# 1. Update user_get_video_detail
# Find where it does the view_count update and comments fetching
search_pattern = r'(\s*)cur\.execute\("SELECT \* FROM video_progress WHERE user_id = \? AND video_id = \? LIMIT 1", \(user_id, int\(video_id\)\)\)'
replacement = r'''\1cur.execute("UPDATE videos SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?", (int(video_id),))
\1conn.commit()
\1video_dict["view_count"] = int(video_dict.get("view_count") or 0) + 1

\1cur.execute("SELECT * FROM video_progress WHERE user_id = ? AND video_id = ? LIMIT 1", (user_id, int(video_id)))'''

content = re.sub(search_pattern, replacement, content, count=1)

# Now find the return block
return_search = r'(\s*)conn\.close\(\)\s*return \{\s*"item": _serialize_video_row\(video_dict, dict\(progress_row\) if progress_row else None, viewer_user_id=user_id\),\s*"related": \[\_serialize_video_row\(r, None, viewer_user_id=user_id\) for r in related_rows\]\s*\}'
return_replacement = r'''\1cur.execute(
\1    "SELECT id, parent_id, like_count, dislike_count, author_name, comment_text, created_at "
\1    "FROM web_video_comments WHERE video_id = ? ORDER BY created_at DESC",
\1    (int(video_id),)
\1)
\1comments = []
\1for cr in cur.fetchall() or []:
\1    comments.append({
\1        "id": int(cr["id"]),
\1        "user_name": str(cr["author_name"]),
\1        "content": str(cr["comment_text"]),
\1        "created_at": _as_iso_timestamp(cr["created_at"])
\1    })
\1item_serialized = _serialize_video_row(video_dict, dict(progress_row) if progress_row else None, viewer_user_id=user_id)
\1item_serialized["comments"] = comments

\1conn.close()
\1return {
\1    "item": item_serialized,
\1    "related": [_serialize_video_row(r, None, viewer_user_id=user_id) for r in related_rows]
\1}'''

content = re.sub(return_search, return_replacement, content, count=1)

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'w') as f:
    f.write(content)

