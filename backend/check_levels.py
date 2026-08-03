import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def run():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT level, COUNT(*) FROM users GROUP BY level;")
    print("Users levels:", c.fetchall())
    c.execute("SELECT level, COUNT(*) FROM groups GROUP BY level;")
    print("Groups levels:", c.fetchall())
    c.execute("SELECT level, COUNT(*) FROM daily_tests_bank GROUP BY level;")
    print("Daily Tests levels:", c.fetchall())
    conn.close()

if __name__ == "__main__":
    run()
