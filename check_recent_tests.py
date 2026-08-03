import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def run():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT level FROM daily_tests_bank ORDER BY id DESC LIMIT 1000")
    rows = c.fetchall()
    counts = Counter(r['level'] for r in rows)
    print("Recent 1000 tests levels:")
    for lvl, count in counts.items():
        print(f"{lvl}: {count}")
    conn.close()

if __name__ == "__main__":
    run()
