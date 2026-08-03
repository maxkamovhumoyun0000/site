import sys

def modify_main():
    with open("backend/main.py", "r") as f:
        content = f.read()

    # 1. Add imports if not present
    if "get_content_test" not in content:
        import_marker = "    create_homework,"
        new_imports = """    get_content_test,
    save_content_test,
    get_content_test_result,
    save_content_test_result,
"""
        content = content.replace(import_marker, new_imports + import_marker)

    # 2. Add Endpoints
    endpoints = """

# --- CONTENT TESTS (VIDEO/BOOK) ---

class ContentTestSaveRequest(BaseModel):
    questions: list[dict]

class ContentTestSubmitRequest(BaseModel):
    answers: dict[str, Any]

@app.get("/admin/{content_type}/{content_id}/test")
async def admin_get_content_test(content_type: str, content_id: int, authorization: str | None = Header(default=None)):
    user = _verify_admin(authorization)
    test = _safe_call(lambda: get_content_test(content_type, content_id), None)
    if not test:
        return {"test": None}
    return {"test": test}

@app.post("/admin/{content_type}/{content_id}/test")
async def admin_save_content_test(content_type: str, content_id: int, payload: ContentTestSaveRequest, authorization: str | None = Header(default=None)):
    user = _verify_admin(authorization)
    saved = _safe_call(lambda: save_content_test(content_type, content_id, json.dumps(payload.questions, ensure_ascii=False), int(user.get("id") or 0)), None)
    if not saved:
        raise HTTPException(status_code=500, detail="Could not save test")
    return {"message": "Test saved", "test": saved}

@app.get("/student/{content_type}/{content_id}/test")
async def student_get_content_test(content_type: str, content_id: int, authorization: str | None = Header(default=None)):
    user = _verify_user(authorization)
    test = _safe_call(lambda: get_content_test(content_type, content_id), None)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Validation based on content type
    user_id = int(user.get("id") or 0)
    if content_type == "video":
        prog = _safe_call(lambda: get_video_progress(user_id, content_id), None)
        if not prog or not prog.get("completed"):
            raise HTTPException(status_code=403, detail="Videoni yakunlangandan keyin test ochiladi")
    elif content_type == "book":
        # Check deadline if applicable
        pass
    
    # Hide correct answers
    if test.get("questions"):
        for q in test["questions"]:
            q.pop("correct", None)
            q.pop("explanation", None)
    
    result = _safe_call(lambda: get_content_test_result(user_id, content_type, content_id), None)
    return {"test": test, "result": result}

@app.post("/student/{content_type}/{content_id}/test")
async def student_submit_content_test(content_type: str, content_id: int, payload: ContentTestSubmitRequest, authorization: str | None = Header(default=None)):
    user = _verify_user(authorization)
    user_id = int(user.get("id") or 0)
    test = _safe_call(lambda: get_content_test(content_type, content_id), None)
    if not test or not test.get("questions"):
        raise HTTPException(status_code=404, detail="Test not found")
        
    if content_type == "video":
        prog = _safe_call(lambda: get_video_progress(user_id, content_id), None)
        if not prog or not prog.get("completed"):
            raise HTTPException(status_code=403, detail="Videoni yakunlangandan keyin test ochiladi")

    questions = test.get("questions") or []
    total = len(questions)
    score = 0
    answers = payload.answers or {}
    
    for idx, q in enumerate(questions):
        ans = str(answers.get(str(idx)) or "").strip()
        if ans and ans == str(q.get("correct") or "").strip():
            score += 1
            
    result = _safe_call(lambda: save_content_test_result(user_id, content_type, content_id, score, total, json.dumps(answers, ensure_ascii=False)), None)
    return {"message": "Test submitted", "result": result}

"""
    if "class ContentTestSaveRequest(BaseModel):" not in content:
        content += endpoints
        with open("backend/main.py", "w") as f:
            f.write(content)
        print("Successfully updated main.py")
    else:
        print("Already updated main.py")

if __name__ == "__main__":
    modify_main()
