import sqlite3

dbs = ['../database.db', '../diamond.db', '../db.sqlite3', '../data/main.db', '../data/database.sqlite']
for db in dbs:
    print(f"--- {db} ---")
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables count:", len(tables))
        if 'videos' in tables:
            cur.execute("SELECT COUNT(*) FROM videos")
            print("Videos count:", cur.fetchone()[0])
            cur.execute("SELECT * FROM videos LIMIT 1")
            row = cur.fetchone()
            if row:
                print("Can query video:", row[0])
                video_id = row[0]
                try:
                    cur.execute("SELECT id, parent_id, like_count, dislike_count, author_name, comment_text, created_at FROM web_video_comments WHERE video_id = ? ORDER BY created_at DESC", (video_id,))
                    print("Comments query SUCCESS")
                except Exception as e:
                    print("Comments query FAILED:", e)
    except Exception as e:
        print(e)
