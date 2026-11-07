from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_test_attempt_only_auto_submits_standalone_test_homework():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    test_submit = source.split(
        "async def _student_submit_content_test_endpoint(", 1
    )[1].split("@app.get(\"/content-tests/", 1)[0]

    assert 'str(homework.get("homework_kind") or "").lower() == "test"' in test_submit
    assert 'if submission and test_only:' in test_submit
    assert 'homework_kind"' in test_submit


def test_final_homework_submit_validates_each_required_component_and_test():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    submit = source.split('@app.post("/student/homework/{homework_id}/submit")', 1)[1]
    submit = submit.split('@app.post("/teacher/homework/{homework_id}/review")', 1)[0]

    assert 'homework.get("requires_essay")' in submit
    assert 'homework.get("requires_file")' in submit
    assert 'homework.get("requires_voice_message")' in submit
    assert 'homework.get("requires_test")' in submit
    assert '_homework_test_result_for_student(user_id, int(homework_id))' in submit
    assert 'str(existing_submission.get("note") or "") == "Test auto-submit"' in submit


def test_only_regular_voice_rooms_require_plus_or_pro_and_homework_is_exempt():
    subscriptions = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'allowed = paid or linked' in subscriptions
    voice_join = main.split('async def websocket_voice_room(', 1)[1]
    assert 'not is_homework_room' in voice_join
    assert 'not is_study_room' in voice_join
    assert 'voice_room_plan_required' in voice_join
