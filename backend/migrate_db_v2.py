import os
from dotenv import load_dotenv
import psycopg

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
url = os.environ.get("DATABASE_URL")

def run():
    print("Connecting to", url)
    conn = psycopg.connect(url)
    conn.autocommit = True
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
        "groups"
    ]
    
    for table in tables:
        try:
            for old_lvl, new_lvl in mapping.items():
                c.execute(f"UPDATE {table} SET level = %s WHERE level = %s", (new_lvl, old_lvl))
            print(f"Updated {table}")
        except Exception as e:
            print(f"Error on {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    run()
