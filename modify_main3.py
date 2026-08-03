import sys

def modify_main():
    with open("backend/main.py", "r") as f:
        content = f.read()

    new_func = """
@app.get("/teacher/{content_type}/{content_id}/test")
async def teacher_get_content_test(content_type: str, content_id: int, authorization: str | None = Header(default=None)):
    user = _verify_teacher(authorization)
    test = _safe_call(lambda: get_content_test(content_type, content_id), None)
    if not test:
        return {"test": None}
    return {"test": test}

@app.post("/teacher/{content_type}/{content_id}/test")
async def teacher_save_content_test(content_type: str, content_id: int, payload: ContentTestSaveRequest, authorization: str | None = Header(default=None)):
    user = _verify_teacher(authorization)
    saved = _safe_call(lambda: save_content_test(content_type, content_id, json.dumps(payload.questions, ensure_ascii=False), int(user.get("id") or 0)), None)
    if not saved:
        raise HTTPException(status_code=500, detail="Could not save test")
    return {"message": "Test saved", "test": saved}
"""
    if "def teacher_save_content_test" not in content:
        import_marker = "class ContentTestSubmitRequest(BaseModel):"
        content = content.replace(import_marker, import_marker + new_func)
        with open("backend/main.py", "w") as f:
            f.write(content)
        print("Successfully updated main.py with teacher endpoints")
    else:
        print("Already updated main.py")

if __name__ == "__main__":
    modify_main()
