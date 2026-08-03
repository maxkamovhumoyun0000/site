import sqlite3, glob

for db in glob.glob("*.db") + glob.glob("*.sqlite3"):
    print(f"--- {db} ---")
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables:", tables)
    except Exception as e:
        print(e)
