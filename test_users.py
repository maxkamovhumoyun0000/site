import sys
from db import get_conn
try:
    conn = get_conn()
    cur = conn.cursor()
    where_sql = ["u.login_type IN (1,2,6)"]
    params = []
    
    query = """
        SELECT
            u.*,
            COALESCE(gc.group_count, 0) AS group_count
        FROM users u
        LEFT JOIN (
            SELECT ug.user_id, COUNT(DISTINCT ug.group_id) AS group_count
            FROM user_groups ug
            LEFT JOIN groups g ON g.id = ug.group_id
            WHERE (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT))='')
              AND (g.id IS NULL OR COALESCE(g.active,1)=1)
            GROUP BY ug.user_id
        ) gc ON gc.user_id = u.id
        WHERE u.login_type IN (1,2,6)
        ORDER BY COALESCE(u.created_at, CURRENT_TIMESTAMP) DESC, u.id DESC
        LIMIT 5
    """
    cur.execute(query)
    rows = cur.fetchall()
    print("Fetched", len(rows), "users")
    for row in rows:
        print(dict(row))
    conn.close()
except Exception as e:
    print("Error:", e)
