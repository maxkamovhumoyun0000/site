import sqlite3

def run():
    conn = sqlite3.connect("db.sqlite3")
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
                c.execute(f"UPDATE {table} SET level = ? WHERE level = ?", (new_lvl, old_lvl))
            print(f"Updated {table}")
        except Exception as e:
            print(f"Error on {table}: {e}")
            
    conn.commit()
    conn.close()

run()
