import asyncio
import json
from backend.main import user_get_videos, student_grammar_topics

async def main():
    try:
        # We need a user to pass the auth header check. 
        # But _user_row_from_bearer uses token. 
        # Let's bypass HTTP layer and call the DB directly to see format.
        
        from db import get_conn
        conn = get_conn()
        conn.row_factory = dict_factory if hasattr(conn, 'row_factory') else None # Need dict factory
        cur = conn.cursor()
        
        # VIDEOS
        print("--- VIDEOS ---")
        cur.execute("SELECT * FROM video_lessons LIMIT 1")
        row = cur.fetchone()
        if row:
            # Replicate serialization
            v = dict(row)
            out = {
                "id": int(v.get("id") or 0),
                "title": str(v.get("title") or ""),
                "thumbnail": str(v.get("thumbnail_url") or ""),
                "duration": str(v.get("duration") or ""),
                "level": str(v.get("level") or ""),
                "views": int(v.get("view_count") or 0),
                "likes": int(v.get("like_count") or 0),
                "is_liked": False,
            }
            print(json.dumps(out, indent=2))
        else:
            print("No videos in DB.")

        # BOOKS
        print("--- BOOKS ---")
        cur.execute("SELECT * FROM books LIMIT 1")
        row = cur.fetchone()
        if row:
            b = dict(row)
            out = {
                "id": int(b.get("id") or 0),
                "title": str(b.get("title") or ""),
                "author": str(b.get("author") or ""),
                "cover_url": str(b.get("cover_url") or ""),
                "level": str(b.get("level") or ""),
                "price": float(b.get("price") or 0.0),
                "is_purchased": True,
                "download_url": None,
            }
            print(json.dumps(out, indent=2))
        else:
            print("No books in DB.")

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d
        
    asyncio.run(main())
