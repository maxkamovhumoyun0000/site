import sqlite3, json

conn = sqlite3.connect('database.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT token FROM user_sessions WHERE is_active = 1 LIMIT 1")
row = cur.fetchone()
if row:
    print(row['token'])
else:
    print("No token")
