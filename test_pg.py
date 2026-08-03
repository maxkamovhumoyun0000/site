import psycopg
import sys
from db import DATABASE_URL, _pg_connect_kwargs
try:
    conn = psycopg.connect(DATABASE_URL, **_pg_connect_kwargs())
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM non_existent_table")
    except Exception as e:
        print("Caught select error:", type(e))
    try:
        conn.commit()
        print("Commit succeeded on failed transaction?!")
    except Exception as e:
        print("Caught commit error:", type(e), e)
except Exception as e:
    print("Outer error:", e)
