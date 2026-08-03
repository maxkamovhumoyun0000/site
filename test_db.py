from db import get_conn
import json
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT * FROM videos LIMIT 1")
col = [d.name for d in cur.description]
print(col)
