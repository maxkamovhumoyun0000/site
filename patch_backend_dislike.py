import re

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'r') as f:
    content = f.read()

# 1. Update _mark_liked_videos_for_user
search_mark = r'''    except Exception:
        for row in rows:
            row\["liked_by_me"\] = False'''
replace_mark = r'''        cur.execute(
            f"SELECT video_id FROM video_dislikes WHERE user_id=? AND video_id IN ({qmarks})",
            (int(user_id), *ids),
        )
        disliked = {int(r.get("video_id") or 0) for r in (cur.fetchall() or [])}
        for row in rows:
            row["disliked_by_me"] = int(row.get("id") or 0) in disliked
    except Exception:
        for row in rows:
            row["liked_by_me"] = False
            row["disliked_by_me"] = False'''

content = re.sub(search_mark, replace_mark, content, count=1)

# 2. Add to _serialize_video_row
search_serialize = r'"like_count": int\(row\.get\("like_count"\) or 0\),'
replace_serialize = r'''"like_count": int(row.get("like_count") or 0),
        "dislike_count": int(row.get("dislike_count") or 0),
        "disliked_by_me": bool(row.get("disliked_by_me")),'''

content = re.sub(search_serialize, replace_serialize, content, count=1)

# 3. Add video_dislikes table
search_table = r'"CREATE TABLE IF NOT EXISTS video_likes \(user_id BIGINT, video_id BIGINT, PRIMARY KEY \(user_id, video_id\)\)",'
replace_table = r'''"CREATE TABLE IF NOT EXISTS video_likes (user_id BIGINT, video_id BIGINT, PRIMARY KEY (user_id, video_id))",
        "CREATE TABLE IF NOT EXISTS video_dislikes (user_id BIGINT, video_id BIGINT, PRIMARY KEY (user_id, video_id))",'''
content = re.sub(search_table, replace_table, content, count=1)

# 4. Add ALTER TABLE videos ADD COLUMN dislike_count
search_alter = r'"ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_risk_score DOUBLE PRECISION DEFAULT 0",'
replace_alter = r'''"ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_risk_score DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE videos ADD COLUMN IF NOT EXISTS dislike_count INTEGER DEFAULT 0",'''
content = re.sub(search_alter, replace_alter, content, count=1)

# 5. Add toggle_video_dislike endpoint
search_toggle_like = r'@app\.post\("/student/videos/\{video_id\}/like"\)\n@app\.post\("/teacher/videos/\{video_id\}/like"\)\n@app\.post\("/support/videos/\{video_id\}/like"\)\nasync def toggle_video_like'

replace_toggle_like = r'''@app.post("/student/videos/{video_id}/dislike")
@app.post("/teacher/videos/{video_id}/dislike")
@app.post("/support/videos/{video_id}/dislike")
async def toggle_video_dislike(video_id: int, authorization: str | None = Header(default=None)):
    user = _user_row_from_bearer(authorization)
    _require_role(user, {"student", "teacher", "support", "admin"})
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id = ? LIMIT 1", (int(video_id),))
    video_row = cur.fetchone()
    if not video_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Video not found")
    if int(video_row.get("is_published") or 0) != 1 and _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or "")) != "admin":
        conn.close()
        raise HTTPException(status_code=404, detail="Video not found")
    if not _media_subject_allowed_for_user(user, dict(video_row)):
        conn.close()
        raise HTTPException(status_code=403, detail="Sizda bu videoni ko'rish huquqi yo'q")
    
    cur.execute("SELECT id FROM video_dislikes WHERE user_id=? AND video_id=? LIMIT 1", (user_id, int(video_id)))
    existing = cur.fetchone()
    disliked = False
    if existing:
        cur.execute("DELETE FROM video_dislikes WHERE user_id=? AND video_id=?", (user_id, int(video_id)))
    else:
        disliked = True
        cur.execute(
            "INSERT INTO video_dislikes (user_id, video_id) VALUES (?, ?) ON CONFLICT (user_id, video_id) DO NOTHING",
            (user_id, int(video_id)),
        )
        cur.execute("DELETE FROM video_likes WHERE user_id=? AND video_id=?", (user_id, int(video_id)))
        
    cur.execute("SELECT COUNT(*) AS c FROM video_dislikes WHERE video_id=?", (int(video_id),))
    dislike_count = int((cur.fetchone() or {}).get("c") or 0)
    cur.execute("UPDATE videos SET dislike_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (dislike_count, int(video_id)))
    
    cur.execute("SELECT COUNT(*) AS c FROM video_likes WHERE video_id=?", (int(video_id),))
    like_count = int((cur.fetchone() or {}).get("c") or 0)
    cur.execute("UPDATE videos SET like_count=? WHERE id=?", (like_count, int(video_id)))
    
    conn.commit()
    conn.close()
    _clear_user_media_caches(user_id)
    return {"disliked": disliked, "dislike_count": dislike_count, "like_count": like_count}

@app.post("/student/videos/{video_id}/like")
@app.post("/teacher/videos/{video_id}/like")
@app.post("/support/videos/{video_id}/like")
async def toggle_video_like'''

content = re.sub(search_toggle_like, replace_toggle_like, content, count=1)

# 6. Update toggle_video_like to remove dislike and update counts
search_like_toggle = r'''    else:
        liked = True
        cur\.execute\(
            "INSERT INTO video_likes \(user_id, video_id\) VALUES \(\?, \?\) ON CONFLICT \(user_id, video_id\) DO NOTHING",
            \(user_id, int\(video_id\)\),
        \)
    cur\.execute\("SELECT COUNT\(\*\) AS c FROM video_likes WHERE video_id=\?", \(int\(video_id\),\)\)
    like_count = int\(\(cur\.fetchone\(\) or \{\}\)\.get\("c"\) or 0\)
    cur\.execute\("UPDATE videos SET like_count=\?, updated_at=CURRENT_TIMESTAMP WHERE id=\?", \(like_count, int\(video_id\)\)\)'''

replace_like_toggle = r'''    else:
        liked = True
        cur.execute(
            "INSERT INTO video_likes (user_id, video_id) VALUES (?, ?) ON CONFLICT (user_id, video_id) DO NOTHING",
            (user_id, int(video_id)),
        )
        cur.execute("DELETE FROM video_dislikes WHERE user_id=? AND video_id=?", (user_id, int(video_id)))
        
    cur.execute("SELECT COUNT(*) AS c FROM video_likes WHERE video_id=?", (int(video_id),))
    like_count = int((cur.fetchone() or {}).get("c") or 0)
    cur.execute("UPDATE videos SET like_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (like_count, int(video_id)))
    
    cur.execute("SELECT COUNT(*) AS c FROM video_dislikes WHERE video_id=?", (int(video_id),))
    dislike_count = int((cur.fetchone() or {}).get("c") or 0)
    cur.execute("UPDATE videos SET dislike_count=? WHERE id=?", (dislike_count, int(video_id)))'''

content = re.sub(search_like_toggle, replace_like_toggle, content, count=1)

# Fix return in toggle_video_like
search_return_like = r'return \{"liked": liked, "like_count": like_count\}'
replace_return_like = r'return {"liked": liked, "like_count": like_count, "disliked": False, "dislike_count": dislike_count}'
content = re.sub(search_return_like, replace_return_like, content, count=1)

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'w') as f:
    f.write(content)

