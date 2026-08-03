import sys

def modify_main():
    with open("backend/main.py", "r") as f:
        content = f.read()

    new_func = """
def get_video_progress(user_id: int, video_id: int) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM video_progress WHERE user_id = ? AND video_id = ? LIMIT 1", (int(user_id), int(video_id)))
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()

"""
    if "def get_video_progress" not in content:
        import_marker = "def _serialize_video_progress_row"
        content = content.replace(import_marker, new_func + import_marker)
        with open("backend/main.py", "w") as f:
            f.write(content)
        print("Successfully updated main.py with get_video_progress")
    else:
        print("Already updated main.py")

if __name__ == "__main__":
    modify_main()
