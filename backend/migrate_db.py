import sys
import os

# add current dir to sys.path so we can import db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def run():
    try:
        conn = get_conn()
    except Exception as e:
        print("Failed to connect:", e)
        return
        
    c = conn.cursor()
    
    mapping = {
        "A1": "BEGINNER",
        "A2": "ELEMENTARY",
        "B1": "PRE-INTERMEDIATE",
        "B2": "INTERMEDIATE",
        "C1": "UPPER-INTERMEDIATE",
        "C2": "ADVANCED"
    }
    
    tables = [
        "daily_tests_bank",
        "arena_questions_bank",
        "words",
        "users",
        "groups",
        "daily_tests_history",
        "duel_sessions"
    ]
    
    for table in tables:
        try:
            for old_lvl, new_lvl in mapping.items():
                c.execute(f"UPDATE {table} SET level = %s WHERE level = %s", (new_lvl, old_lvl))
            print(f"Updated {table}")
        except Exception as e:
            print(f"Error on {table}: {e}")
            conn.rollback()
            continue
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run()
