import re

with open("/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py", "r") as f:
    content = f.read()

pattern_get = re.compile(
    r'@app\.get\("/survey/\{survey_id\}"\)\s*async def get_survey_public\(survey_id: int, authorization: str \| None = Header\(default=None\)\):\s*user = _user_row_from_bearer\(authorization\)\s*_ensure_web_tables\(\)\s*conn = get_conn\(\)\s*cur = conn\.cursor\(\)\s*cur\.execute\("SELECT id, title, description, questions_json, status FROM web_surveys WHERE id=\?", \(int\(survey_id\),\)\)\s*survey = _row_to_dict\(cur\.fetchone\(\)\)\s*if not survey:\s*conn\.close\(\)\s*raise HTTPException\(status_code=404, detail="Survey not found"\)\s*cur\.execute\("SELECT id FROM web_survey_responses WHERE survey_id=\? AND user_id=\?", \(int\(survey_id\), int\(user\.get\("id"\) or 0\)\)\)\s*has_responded = bool\(cur\.fetchone\(\)\)\s*conn\.close\(\)\s*return \{"survey": survey, "has_responded": has_responded\}'
)

repl_get = """@app.get("/survey/{survey_id}")
async def get_survey_public(survey_id: int, authorization: str | None = Header(default=None)):
    user = None
    if authorization and authorization != "Bearer null":
        try:
            user = _user_row_from_bearer(authorization)
        except Exception:
            pass
    _ensure_web_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, questions_json, status FROM web_surveys WHERE id=?", (int(survey_id),))
    survey = _row_to_dict(cur.fetchone())
    if not survey:
        conn.close()
        raise HTTPException(status_code=404, detail="Survey not found")

    has_responded = False
    if user:
        cur.execute("SELECT id FROM web_survey_responses WHERE survey_id=? AND user_id=?", (int(survey_id), int(user.get("id") or 0)))
        has_responded = bool(cur.fetchone())
    conn.close()

    return {"survey": survey, "has_responded": has_responded}"""

content = pattern_get.sub(repl_get, content)

pattern_post = re.compile(
    r'@app\.post\("/survey/\{survey_id\}/submit"\)\s*async def submit_survey\(survey_id: int, payload: SurveySubmitRequest, authorization: str \| None = Header\(default=None\)\):\s*user = _user_row_from_bearer\(authorization\)\s*_ensure_web_tables\(\)\s*conn = get_conn\(\)\s*cur = conn\.cursor\(\)\s*try:\s*cur\.execute\(\s*"""\s*INSERT INTO web_survey_responses \(survey_id, user_id, answers_json\)\s*VALUES \(\?, \?, \?\)\s*""",\s*\(int\(survey_id\), int\(user\.get\("id"\) or 0\), json\.dumps\(payload\.answers\)\)\s*\)\s*conn\.commit\(\)\s*except Exception as e:\s*conn\.close\(\)\s*if "UNIQUE" in str\(e\) or "unique" in str\(e\)\.lower\(\):\s*raise HTTPException\(status_code=400, detail="You have already submitted this survey"\)\s*raise HTTPException\(status_code=500, detail=str\(e\)\)\s*conn\.close\(\)\s*return \{"message": "Success"\}'
)

repl_post = """@app.post("/survey/{survey_id}/submit")
async def submit_survey(survey_id: int, payload: SurveySubmitRequest, authorization: str | None = Header(default=None)):
    user = None
    if authorization and authorization != "Bearer null":
        try:
            user = _user_row_from_bearer(authorization)
        except Exception:
            pass
    _ensure_web_tables()
    conn = get_conn()
    cur = conn.cursor()
    import random
    uid = int(user.get("id") or 0) if user else random.randint(-2000000000, -1)
    try:
        cur.execute(
            '''
            INSERT INTO web_survey_responses (survey_id, user_id, answers_json)
            VALUES (?, ?, ?)
            ''',
            (int(survey_id), uid, json.dumps(payload.answers))
        )
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e) or "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="You have already submitted this survey")
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"message": "Success"}"""

content = pattern_post.sub(repl_post, content)

with open("/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py", "w") as f:
    f.write(content)

