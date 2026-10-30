"""Arena/Duel runtime API contracts for the Student and Speaking mobile apps.

Stdlib only: no FastAPI, database or network, and no import of backend
modules. Pure helpers are executed from backend/main.py through ``ast``; route
bodies are checked statically. Run with pytest or with plain
``python3 tests/test_arena_runtime_contracts.py``.

What is checked:
* per-user results carry ``skipped``, ``score`` and ``rank`` (ties share a
  place) without mutating stored session data;
* ``/competition/runtime/{id}/result`` returns ``participants`` (current user
  first, then by rank) next to the old ``participants_result``;
* live lists keep ``remained``/``left`` and add ``participants`` objects that
  expose only progress counts;
* ``/arena/battles`` reads real reward/fee/player values and reports a real
  ``online_count``;
* an explicit ``skipped`` answer on a vocabulary question needs no answer,
  is never graded and is recorded as unanswered, like an MCQ skip;
* the retired Teacher Arena is gone from the backend and the teacher bot;
* the Speaking admin allow-list includes ``/speaking-lp/staff/``.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

ROUTE_DECORATOR_RE = re.compile(r'@(?:app|router)\.(get|post|put|patch|delete)\(\s*"([^"]+)"')

_MAIN_SOURCE: str | None = None
_MAIN_TREE: ast.Module | None = None


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _main() -> tuple[str, ast.Module]:
    global _MAIN_SOURCE, _MAIN_TREE
    if _MAIN_SOURCE is None or _MAIN_TREE is None:
        _MAIN_SOURCE = _read("backend/main.py")
        _MAIN_TREE = ast.parse(_MAIN_SOURCE)
    return _MAIN_SOURCE, _MAIN_TREE


def _load_main_symbols(names: set[str], extra_globals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute only the selected top-level definitions of backend/main.py."""
    _, tree = _main()
    selected: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            hit = [t.id for t in node.targets if isinstance(t, ast.Name) and t.id in names]
            if hit:
                selected.append(node)
                found.update(hit)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            selected.append(node)
            found.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            selected.append(node)
            found.add(node.name)
    missing = names - found
    assert not missing, f"backend/main.py is missing {sorted(missing)}"
    namespace: dict[str, Any] = {"Any": Any, "re": re}
    namespace.update(extra_globals or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), "backend/main.py", "exec"), namespace)
    return namespace


def _main_function_source(name: str) -> str:
    source, tree = _main()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"{name} not found in backend/main.py")


def _route_function_source(method: str, path: str) -> str:
    """Source of the FastAPI handler registered for ``method path`` in main.py."""
    source, tree = _main()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == method
                and deco.args
                and isinstance(deco.args[0], ast.Constant)
                and deco.args[0].value == path
            ):
                segment = ast.get_source_segment(source, node)
                assert segment
                return segment
    raise AssertionError(f"route {method.upper()} {path} not found in backend/main.py")


RESULT_HELPERS = {
    "_competition_rank_positions",
    "_competition_result_rank_map",
    "_competition_client_result",
    "_competition_user_result",
    "_competition_joined_participants",
    "_competition_participant_level",
    "_competition_participant_team",
    "_competition_result_participant_cards",
    "_competition_questions_for_user",
    "_competition_live_lists",
}


def _helpers() -> dict[str, Any]:
    return _load_main_symbols(RESULT_HELPERS)


def _finished_duel_session() -> dict[str, Any]:
    return {
        "id": "cmp_test",
        "mode": "duel-3v3",
        "level": "B1",
        "status": "finished",
        "questions": [{"id": i} for i in range(10)],
        "teams": {1: 1, 2: 1, 3: 2, 4: 2},
        "participants": [
            {"user_id": 1, "name": "Ali", "status": "finished", "level": "A2"},
            {"user_id": 2, "name": "Vali", "status": "finished"},
            {"user_id": 3, "name": "Gani", "status": "finished"},
            {"user_id": 4, "name": "Soli", "status": "left"},
        ],
        "progress": {
            1: {"index": 11, "correct": 6, "wrong": 3, "unanswered": 1},
            2: {"index": 11, "correct": 8, "wrong": 2, "unanswered": 0},
            3: {"index": 11, "correct": 6, "wrong": 3, "unanswered": 1},
            4: {"index": 4, "correct": 2, "wrong": 1, "unanswered": 0},
        },
        "result": {
            "winners": [3, 4],
            "tie": False,
            "by_user": {
                1: {"correct": 6, "wrong": 3, "unanswered": 1, "winner": False, "result_status": "lose", "team": 1},
                2: {"correct": 8, "wrong": 2, "unanswered": 0, "winner": False, "result_status": "lose", "team": 1},
                "3": {"correct": 6, "wrong": 3, "unanswered": 1, "winner": True, "result_status": "win", "team": 2},
                4: {"correct": 2, "wrong": 1, "unanswered": 7, "winner": True, "result_status": "win", "team": 2},
            },
        },
    }


# --------------------------------------------------------------------------
# a) skipped / score / rank on every per-user result
# --------------------------------------------------------------------------

def test_rank_positions_order_and_ties():
    rank = _helpers()["_competition_rank_positions"]
    ranks = rank([(10, 5, 0), (11, 5, 0), (12, 4, 1), (13, 4, 2), (14, 7, 9)])
    assert ranks == {14: 1, 10: 2, 11: 2, 12: 4, 13: 5}
    # wrong is the tie-breaker when correct is equal.
    assert rank([(1, 3, 2), (2, 3, 1)]) == {2: 1, 1: 2}
    assert rank([]) == {}


def test_user_result_adds_skipped_score_rank_without_mutation():
    ns = _helpers()
    session = _finished_duel_session()
    stored_before = {k: dict(v) for k, v in session["result"]["by_user"].items()}
    own = ns["_competition_user_result"](session, 1)
    assert own["skipped"] == 1 and own["unanswered"] == 1
    assert own["score"] == 6
    assert own["rank"] == 2  # user 2 has 8 correct; users 1 and 3 tie on 6/3
    assert ns["_competition_user_result"](session, 3)["rank"] == 2  # str key, tie shares place
    assert ns["_competition_user_result"](session, 4)["rank"] == 4
    assert ns["_competition_user_result"](session, 2)["rank"] == 1
    # Stored data is untouched (old sessions are enriched on read only).
    assert session["result"]["by_user"] == stored_before
    assert ns["_competition_user_result"](session, 99) is None


def test_cancelled_results_have_null_rank():
    ns = _helpers()
    session = _finished_duel_session()
    session["result"] = {
        "winners": [],
        "error": "session_timeout",
        "refunded": True,
        "by_user": {
            1: {"rank": None, "correct": 0, "wrong": 0, "unanswered": 0, "result_status": "cancelled", "error": "session_timeout"},
        },
    }
    own = ns["_competition_user_result"](session, 1)
    assert own["rank"] is None and own["skipped"] == 0 and own["score"] == 0


def test_daily_stored_rank_is_kept_and_eliminated_follow():
    ns = _helpers()
    session = {
        "mode": "daily",
        "level": "A2",
        "participants": [{"user_id": u, "name": f"U{u}", "status": "finished"} for u in (1, 2, 3, 4)],
        "progress": {},
        "result": {
            "winners": [2],
            "by_user": {
                1: {"rank": 2, "correct": 9, "wrong": 1, "unanswered": 0},
                2: {"rank": 1, "correct": 8, "wrong": 2, "unanswered": 0},
                3: {"rank": None, "correct": 20, "wrong": 5, "unanswered": 3, "eliminated": True},
                4: {"rank": None, "correct": 25, "wrong": 5, "unanswered": 0, "eliminated": True},
            },
        },
    }
    get = ns["_competition_user_result"]
    assert get(session, 2)["rank"] == 1 and get(session, 1)["rank"] == 2
    assert get(session, 4)["rank"] == 3 and get(session, 3)["rank"] == 4


def test_result_participants_result_rows_carry_new_fields():
    source = _main_function_source("_competition_result_participants")
    for key in ('"skipped": skipped', '"score": int(own.get("correct") or 0)', '"rank":', '"unanswered": skipped'):
        assert key in source


# --------------------------------------------------------------------------
# b) /result participants
# --------------------------------------------------------------------------

PARTICIPANT_CARD_KEYS = {
    "user_id", "name", "level", "team", "status", "correct", "wrong",
    "skipped", "score", "rank", "is_winner", "is_me",
}


def test_result_participant_cards_shape_and_order():
    ns = _helpers()
    cards = ns["_competition_result_participant_cards"](_finished_duel_session(), 3)
    assert [c["user_id"] for c in cards] == [3, 2, 1, 4]  # me first, then by rank, then name
    for card in cards:
        assert set(card) == PARTICIPANT_CARD_KEYS
    me = cards[0]
    assert me["is_me"] is True and me["is_winner"] is True and me["rank"] == 2 and me["team"] == 2
    assert all(c["is_me"] is False for c in cards[1:])
    by_id = {c["user_id"]: c for c in cards}
    assert by_id[1]["level"] == "A2"  # stored at join time
    assert by_id[2]["level"] == "B1"  # falls back to session level
    assert by_id[4]["skipped"] == 7 and by_id[4]["score"] == 2 and by_id[4]["status"] == "left"


def test_result_route_returns_participants_and_keeps_old_keys():
    source = _route_function_source("get", "/competition/runtime/{session_id}/result")
    assert source.count('"participants": _competition_result_participant_cards(sess, uid)') == 2
    assert source.count('"participants_result": _competition_result_participants(sess)') == 2
    # The cancelled/refunded result shape also carries the new fields.
    error_block = source.split('"error": session_result.get("error") or "Queue expired"', 1)[0]
    for key in ('"skipped": 0', '"score": 0', '"rank": None'):
        assert key in error_block


# --------------------------------------------------------------------------
# c) live lists
# --------------------------------------------------------------------------

LIVE_PARTICIPANT_KEYS = {
    "user_id", "name", "status", "team", "level", "score",
    "completed_count", "total_questions", "progress_percent",
}


def test_live_lists_keep_names_and_add_participant_objects():
    ns = _helpers()
    session = _finished_duel_session()
    session["status"] = "running"
    for row in session["participants"][:3]:
        row["status"] = "active"
    live = ns["_competition_live_lists"](session)
    assert live["remained"] == ["Ali", "Vali", "Gani"] and live["left"] == ["Soli"]
    assert all(isinstance(name, str) for name in live["remained"] + live["left"])
    rows = live["participants"]
    assert [r["user_id"] for r in rows] == [1, 2, 3, 4]
    for row in rows:
        assert set(row) == LIVE_PARTICIPANT_KEYS  # counts only: no answers or options
    soli = rows[3]
    assert soli["score"] == 2 and soli["completed_count"] == 3 and soli["total_questions"] == 10
    assert soli["progress_percent"] == 30 and soli["team"] == 2 and soli["level"] == "B1"

    mine = ns["_competition_live_lists"](session, current_user_id=3)
    assert mine["participants"][0]["user_id"] == 3 and mine["participants"][0]["is_me"] is True
    assert all(r["is_me"] is False for r in mine["participants"][1:])
    assert set(mine["participants"][0]) == LIVE_PARTICIPANT_KEYS | {"is_me"}


def test_every_route_passes_current_user_to_live_lists():
    source, _ = _main()
    calls = re.findall(r"_competition_live_lists\(([^)]*)\)", source)
    calls = [c for c in calls if not c.startswith("session: dict")]
    assert calls, "no _competition_live_lists calls found"
    for args in calls:
        assert "current_user_id=uid" in args, f"_competition_live_lists({args}) does not pass the current user"


# --------------------------------------------------------------------------
# d) participant level
# --------------------------------------------------------------------------

def test_start_route_stores_participant_level_and_snapshot_fills_it():
    start = _route_function_source("post", "/competition/runtime/start")
    append = re.search(r"participants\.append\(\{[^\n]*\}\)", start)
    assert append and '"level": level' in append.group(0)
    snapshot = _main_function_source("_competition_snapshot")
    assert '"level": _competition_participant_level(session, raw_participant_rows.get(' in snapshot


# --------------------------------------------------------------------------
# e) /arena/battles
# --------------------------------------------------------------------------

def test_arena_battles_use_real_values():
    source = _route_function_source("get", "/arena/battles")
    assert not re.search(r'"reward"\s*:\s*(18|22|28|24)\b', source), "hardcoded battle rewards are back"
    for key in (
        '"entry_fee": float(_competition_entry_fee(mode))',
        '"required_players": required_players',
        '"max_players":',
        '"mode": mode',
        '"daily_limit": int(COMPETITION_DAILY_JOIN_LIMIT)',
        '"used_today":',
        '"online_count": _online_student_count()',
        '"subjects": _user_subjects_from_row(user)',
        "_competition_rule_settings()",
        'rules.get("duel_reward")',
        'rules.get("boss_arena_reward_flat")',
    ):
        assert key in source, f"/arena/battles is missing {key}"
    for key in ('"id": battle["id"]', '"title":', '"description":', '"opponent":', '"status": "open"'):
        assert key in source, f"/arena/battles dropped {key}"
    # The catalog only holds presentation text, never numbers.
    catalog = _load_main_symbols({"_ARENA_BATTLE_CATALOG"})["_ARENA_BATTLE_CATALOG"]
    assert [item["id"] for item in catalog] == ["duel-1v1", "duel-3v3", "duel-5v5", "boss-arena"]
    assert all(isinstance(value, str) for item in catalog for value in item.values())


def test_rule_settings_expose_paid_boss_reward():
    rules = _main_function_source("_competition_rule_settings")
    finalize = _main_function_source("_competition_finalize_non_daily")
    assert '"boss_arena_reward_flat": max(0.0, float(settings.get("boss_arena_reward_flat") or 20.0))' in rules
    assert 'float(settings.get("boss_arena_reward_flat") or 20.0)' in finalize
    assert '"duel_reward": float(settings.get("duel_reward") or settings.get("arena_reward") or 5.0)' in rules


def test_online_count_reads_presence_sessions():
    source = _main_function_source("_online_student_count")
    assert "FROM web_user_sessions" in source
    assert "revoked_at IS NULL" in source and "last_seen_at >= ?" in source
    assert "ONLINE_PRESENCE_WINDOW_SECONDS" in source
    assert "return None" in source  # unreadable presence is reported, not faked


# --------------------------------------------------------------------------
# f) opponent progress while waiting
# --------------------------------------------------------------------------

def test_status_question_answer_expose_opponent_progress():
    status = _route_function_source("get", "/competition/runtime/{session_id}/status")
    assert status.count('out["opponent_progress"] = _competition_opponent_progress(sess, uid)') == 2
    question = _route_function_source("get", "/competition/runtime/{session_id}/question")
    assert question.count('"opponent_progress":') >= 2
    answer = _route_function_source("post", "/competition/runtime/{session_id}/answer")
    assert '"waiting_completion": True' in answer
    assert 'out["waiting_completion"] = True' in answer
    assert '"opponent_progress": _competition_opponent_progress(sess, uid)' in answer
    assert 'out["opponent_progress"] = _competition_opponent_progress(sess, uid)' in answer
    payload = _main_function_source("_competition_current_question_payload")
    assert '"opponent_progress": _competition_opponent_progress(session, uid)' in payload


# --------------------------------------------------------------------------
# f2) explicit skip on vocabulary questions
# --------------------------------------------------------------------------

def test_answer_route_treats_skip_like_timeout_and_records_unanswered():
    source, _ = _main()
    model = source.split("class CompetitionAnswerRequest(BaseModel):", 1)[1].split("\nclass ", 1)[0]
    assert "timed_out: bool = False" in model and "skipped: bool = False" in model
    route = _route_function_source("post", "/competition/runtime/{session_id}/answer")
    pregrade, recording = route.split("with _competition_session_advisory_lock(actual_sid):", 1)
    # Pregrade: a skip needs no answer (like a timeout) and never reaches the grader.
    assert "no_answer_required = bool(payload.skipped) or timeout_submission" in pregrade
    assert pregrade.count("if not no_answer_required and pre_type") == 3
    assert "if not timeout_submission and" not in pregrade
    no_answer_branch = pregrade.split("if no_answer_required:", 1)[1]
    assert no_answer_branch.lstrip().startswith("pregraded_correct = False")
    assert no_answer_branch.index("else:") < no_answer_branch.index("_competition_grade_vocabulary_answer(")
    # Recording: a skip takes the MCQ-skip path (no selection, no submission,
    # no stored answer, no grading override).
    for snippet in (
        "skip_submission = bool(payload.skipped)",
        "sel = None if skip_submission else payload.selected_option_index",
        "has_non_option_answer = not skip_submission and bool(",
        "keep_special_answer = is_special_answer and not skip_submission",
        "submitted=(has_non_option_answer if is_special_answer else sel is not None)",
        "if keep_special_answer and pregraded_question_index == q_index",
        "answer_text=payload.answer_text if keep_special_answer else None",
        "audio_url=payload.audio_url if keep_special_answer else None",
        "matching_answer=payload.matching_answer if keep_special_answer else None",
    ):
        assert snippet in recording, f"answer route lost: {snippet}"


def _apply_outcome(question: dict[str, Any], **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run _competition_apply_question_outcome for question 1 with DB writes stubbed."""
    import json

    recorded: list[dict[str, Any]] = []

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: Any = None) -> None:
            super().__init__(detail)
            self.status_code = status_code

    class _Personalization:
        @staticmethod
        def record_test_mistake(**_kwargs: Any) -> None:
            return None

    def _persist(_session: Any, uid: int, q_index: int, selected: Any, **fields: Any) -> None:
        recorded.append({"user_id": uid, "question_index": q_index, "selected": selected, **fields})

    ns = _load_main_symbols(
        {"_competition_apply_question_outcome", "_competition_user_progress", "_competition_questions_for_user", "_duel_is_mode"},
        {
            "HTTPException": _HTTPException,
            "json": json,
            "_duel_persist_answer": _persist,
            "personalization_api": _Personalization,
            "_competition_seed_question_timer": lambda *a, **k: None,
            "_competition_seed_round_timers": lambda *a, **k: None,
            "_selected_option_is_correct": lambda _q, idx: int(idx) == 1,
            "_safe_call": lambda _fn, fallback: fallback,
            "_now_utc": lambda: None,
        },
    )
    session = {
        "id": "cmp_skip",
        "mode": "duel-1v1",
        "questions": [question, {"id": 2}],
        "progress": {7: {"index": 1, "correct": 0, "wrong": 0, "unanswered": 0}},
    }
    timer = {"is_late": False, "allowed_seconds": 30, "deadline_at": "2026-10-28T09:00:30+00:00"}
    assert ns["_competition_apply_question_outcome"](session, 7, 1, None, timer, **kwargs) is True
    assert len(recorded) == 1
    return session["progress"][7], recorded[0]


def test_vocabulary_skip_is_recorded_like_an_mcq_skip():
    vocabulary = {"id": 1, "question_type": "spelling", "input": "text"}
    mcq = {"id": 1, "question_type": "multiple_choice", "options": ["a", "b", "c", "d"], "correct_option_index": 2}
    # Exactly the arguments the answer route passes for a skip / an MCQ null answer.
    skip_args = {"submitted": False, "is_correct_override": None, "answer_text": None, "audio_url": None, "matching_answer": None}
    vocab_progress, vocab_row = _apply_outcome(vocabulary, **skip_args)
    mcq_progress, mcq_row = _apply_outcome(mcq, **skip_args)
    assert vocab_progress == mcq_progress == {"index": 2, "correct": 0, "wrong": 0, "unanswered": 1}
    assert vocab_row == mcq_row
    assert vocab_row["is_unanswered"] is True and vocab_row["is_correct"] is False
    assert vocab_row["selected"] is None and vocab_row["answer_text"] is None and vocab_row["matching_answer"] is None
    # An unsubmitted answer is never counted as correct, whatever the pregrade says.
    progress, row = _apply_outcome(vocabulary, submitted=False, is_correct_override=True)
    assert progress["correct"] == 0 and progress["unanswered"] == 1 and row["is_correct"] is False
    # Control: a real submission with a correct pregrade is still counted.
    progress, row = _apply_outcome(vocabulary, submitted=True, is_correct_override=True, answer_text="apple")
    assert progress["correct"] == 1 and progress["unanswered"] == 0 and row["is_correct"] is True


# --------------------------------------------------------------------------
# g) Speaking app accounts keep passing every competition route
# --------------------------------------------------------------------------

def test_competition_routes_use_speaking_aware_access_gate():
    _, tree = _main()
    checked = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths = [
            deco.args[0].value
            for deco in node.decorator_list
            if isinstance(deco, ast.Call) and deco.args and isinstance(deco.args[0], ast.Constant)
            and isinstance(deco.args[0].value, str)
        ]
        if not any(p.startswith("/competition/runtime") or p == "/arena/battles" for p in paths):
            continue
        source = _main_function_source(node.name)
        assert "_require_competition_learning_access(user)" in source, f"{paths} lost the competition access gate"
        assert "_require_student_learning_access(" not in source, f"{paths} adds a student-group check"
        checked += 1
    assert checked >= 8
    gate = _main_function_source("_require_competition_learning_access")
    assert 'is_speaking_app_account(user.get("speaking_app_account"))' in gate


# --------------------------------------------------------------------------
# Retired Teacher Arena
# --------------------------------------------------------------------------

def test_no_teacher_arena_route_remains():
    for path in sorted(BACKEND.glob("*.py")):
        for method, route in ROUTE_DECORATOR_RE.findall(path.read_text(encoding="utf-8")):
            assert not route.startswith("/teacher/arena"), f"{path.name} still registers {method.upper()} {route}"
    source, tree = _main()
    gone = {
        "TeacherArenaStartRequest",
        "TeacherArenaGenerationRequest",
        "_stage_manual_group_arena_questions",
        "_ensure_group_arena_generation_jobs_schema",
        "_save_group_arena_generation_job",
        "_get_group_arena_generation_job",
        "_run_group_arena_generation_job",
        "_latest_legacy_group_arena_session",
        "_auto_close_stale_arena_group_session",
    }
    defined = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert not (gone & defined), f"retired Teacher Arena helpers remain: {sorted(gone & defined)}"
    assert '"arena_sessions": active_arenas' not in source
    # Kept: the student runtime still depends on these.
    for name in ("_mark_legacy_group_arena_completed", "_group_arena_today_presence"):
        assert name in defined
    middleware = _main_function_source("block_retired_arena_routes")
    assert 'path.startswith("/teacher/arena/")' not in middleware
    assert '"arena-group", "arena-daily"' in middleware
    job_status = _route_function_source("get", "/teacher/generator/jobs/{job_id}")
    assert '!= "arena"' not in job_status


def test_teacher_bot_and_i18n_drop_teacher_arena():
    bot = _read("teacher_bot.py")
    for marker in ("teacher_arena", "teacher_group_arena", "_format_teacher_arena_live_text", "_refresh_teacher_arena_message"):
        assert marker not in bot, f"teacher_bot.py still contains {marker}"
    i18n = _read("i18n.py")
    assert not re.search(r"['\"]teacher_(?:group_)?arena_[a-z0-9_]*['\"]\s*:", i18n)
    ast.parse(bot)
    ast.parse(i18n)


# --------------------------------------------------------------------------
# Speaking admin workspace allow-list
# --------------------------------------------------------------------------

def test_speaking_lp_staff_prefix_is_allowed_for_speaking_admin():
    ns = _load_main_symbols(
        {
            "_SPEAKING_ADMIN_WORKSPACE_PATHS",
            "_SPEAKING_ADMIN_WORKSPACE_PREFIXES",
            "_NOTIFICATION_READ_PATH_RE",
            "_speaking_admin_workspace_path_is_allowed",
        }
    )
    assert "/speaking-lp/staff/" in ns["_SPEAKING_ADMIN_WORKSPACE_PREFIXES"]
    allowed = ns["_speaking_admin_workspace_path_is_allowed"]
    assert allowed("/speaking-lp/staff/paths")
    assert allowed("/speaking-lp/staff/paths/12/modules")
    # Student routes are for speaking users, not part of the admin workspace.
    assert not allowed("/speaking-lp/student/paths")
    assert not allowed("/admin/payments")


def test_round_barrier_releases_together_and_excludes_offline_players():
    from datetime import datetime, timezone

    started = datetime(2026, 10, 30, tzinfo=timezone.utc)
    seeded = []
    ns = _load_main_symbols(
        {
            "_competition_user_progress", "_competition_questions_for_user",
            "_competition_round_index", "_competition_waiting_for_round",
            "_competition_seed_round_timers",
        },
        {
            "_now_utc": lambda: started,
            "_competition_seed_question_timer": lambda _s, uid, index, _q, **kw:
                seeded.append((uid, index, kw["started_at"])),
        },
    )
    session = {
        "mode": "duel-1v1", "questions": [{"id": 1}, {"id": 2}],
        "participants": [{"user_id": 1, "status": "active"}, {"user_id": 2, "status": "active"}],
        "progress": {"1": {"index": 2}, "2": {"index": 1}},
    }
    assert ns["_competition_waiting_for_round"](session, 1)
    assert not ns["_competition_waiting_for_round"](session, 2)
    ns["_competition_seed_round_timers"](session)
    assert seeded == [(2, 1, started)]
    seeded.clear()
    session["progress"]["2"]["index"] = 2
    assert not ns["_competition_waiting_for_round"](session, 1)
    ns["_competition_seed_round_timers"](session)
    assert seeded == [(1, 2, started), (2, 2, started)]
    session["progress"]["2"]["index"] = 1
    session["participants"][1]["status"] = "left"
    assert not ns["_competition_waiting_for_round"](session, 1)


def test_offline_player_is_removed_from_round_before_question_timeout():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    persisted = []
    ns = _load_main_symbols(
        {
            "_competition_user_progress", "_competition_questions_for_user",
            "_competition_participant_row", "_competition_round_index",
            "_competition_waiting_for_round", "_competition_auto_skip_due_questions",
            "_COMPETITION_EXPLICIT_LEFT_REASONS",
        },
        {
            "_competition_session_phase": lambda _s: "active",
            "_parse_utc_timestamp": lambda value: datetime.fromisoformat(value) if value else None,
            "_now_utc": lambda: now,
            "timedelta": timedelta,
            "_competition_seed_round_timers": lambda _s: None,
            "_duel_persist_session": lambda s: persisted.append(s["id"]),
            "_competition_finalize_if_all_progress_finished": lambda _s: False,
            "_competition_finish_user_remaining_questions": lambda *_a, **_k: False,
            "_competition_timer_state": lambda *_a, **_k: {"deadline_at": (now + timedelta(seconds=30)).isoformat()},
        },
    )
    session = {
        "id": "cmp_presence", "mode": "duel-1v1", "questions": [{"id": 1}, {"id": 2}],
        "participants": [
            {"user_id": 1, "status": "active", "runtime_presence": True, "last_ping_at": now.isoformat()},
            {"user_id": 2, "status": "active", "runtime_presence": True, "last_ping_at": (now - timedelta(seconds=16)).isoformat()},
        ],
        "progress": {"1": {"index": 2}, "2": {"index": 1}},
    }
    assert ns["_competition_auto_skip_due_questions"](session, now)
    assert session["participants"][1]["left_reason"] == "offline_timeout"
    assert not ns["_competition_waiting_for_round"](session, 1)
    assert session["progress"]["2"]["index"] == 1  # can catch up on rejoin
    assert persisted


def test_rejoining_player_skips_missed_rounds_and_rejoins_current_round():
    from datetime import datetime, timezone
    import logging

    skipped = []

    def apply_outcome(session, uid, index, _selected, _timer, **_kwargs):
        skipped.append(index)
        session["progress"][str(uid)]["index"] = index + 1
        return True

    ns = _load_main_symbols(
        {
            "_competition_user_progress", "_competition_questions_for_user",
            "_competition_participant_row", "_competition_round_index",
            "_competition_restore_runtime_participant_if_needed",
            "_COMPETITION_TERMINAL_PARTICIPANT_STATUSES",
            "_COMPETITION_EXPLICIT_LEFT_REASONS", "_COMPETITION_RESTORABLE_LEFT_REASONS",
        },
        {
            "_competition_session_phase": lambda _s: "active",
            "_competition_user_result": lambda *_a: None,
            "_competition_apply_question_outcome": apply_outcome,
            "_now_utc": lambda: datetime(2026, 10, 30, tzinfo=timezone.utc),
            "_duel_persist_session": lambda _s: None,
            "WEB_DUEL_PLAYER_SESSION": {},
            "logger": logging.getLogger(__name__),
        },
    )
    session = {
        "id": "cmp_rejoin", "mode": "duel-1v1", "questions": [{"id": 1}, {"id": 2}, {"id": 3}],
        "participants": [
            {"user_id": 1, "status": "active"},
            {"user_id": 2, "status": "left", "left_reason": "offline_timeout"},
        ],
        "progress": {"1": {"index": 3}, "2": {"index": 1}},
    }
    assert ns["_competition_restore_runtime_participant_if_needed"](session, 2)
    assert skipped == [1, 2]
    assert session["progress"]["2"]["index"] == 3
    assert session["participants"][1]["status"] == "active"


if __name__ == "__main__":
    import sys
    import traceback

    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except Exception:  # noqa: BLE001 - report every failing contract
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
