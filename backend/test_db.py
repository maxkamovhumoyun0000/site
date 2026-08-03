import sqlite3

try:
    conn = sqlite3.connect('database.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos LIMIT 1")
    row = cur.fetchone()
    if row:
        video_id = row[0]
        cur.execute("SELECT id, parent_id, like_count, dislike_count, author_name, comment_text, created_at FROM web_video_comments WHERE video_id = ? ORDER BY created_at DESC", (video_id,))
        print("Success")
except Exception as e:
    print(f"Error: {e}")
