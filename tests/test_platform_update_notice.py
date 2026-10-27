"""Contract tests for scripts/send_platform_update_notice.py.

Stdlib only: no database, Firebase or network. The script runs against an
in-memory fake ``db`` connection and fake ``push_notifications`` /
``firebase_admin`` modules. Run with pytest or with plain
``python3 tests/test_platform_update_notice.py``.

What is checked:
* the script parses and never imports backend/main.py or sends Telegram;
* the owner's UZ/RU/EN texts are used exactly, UZ then RU then EN, and fit
  the backend and FCM limits;
* the idempotency key, the popup type ("broadcast") and the push data match
  what the backend and the apps use;
* running without ``--send`` (or with ``--dry-run``) writes nothing and sends
  nothing;
* ``--send`` creates only missing inbox items, pushes once per new item in
  the user's language, sends the Speaking announcement once, and a second run
  does nothing.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "send_platform_update_notice.py"

UZ_TITLE = "Muhim: platforma yangilanmoqda"
UZ_BODY = (
    "Hurmatli foydalanuvchi! Diamond Education platformasida xavfsizlikni kuchaytirish va yangi imkoniyatlarni "
    "qo'shish ishlari olib borilmoqda. Shu sababli Student, Speaking va Teacher ilovalarining ayrim bo'limlari "
    "ilovangiz yangilanmaguncha to'liq yoki to'g'ri ishlamasligi mumkin. Iltimos, ilovani App Store yoki Google "
    "Play orqali yangilang. Noqulaylik uchun uzr so'raymiz."
)
RU_TITLE = "Важно: платформа обновляется"
RU_BODY = (
    "Уважаемый пользователь! На платформе Diamond Education проводятся работы по усилению безопасности и "
    "добавлению новых функций. Поэтому некоторые разделы приложений Student, Speaking и Teacher могут работать "
    "не полностью или некорректно, пока вы не обновите приложение. Пожалуйста, обновите приложение через App "
    "Store или Google Play. Приносим извинения за неудобства."
)
EN_TITLE = "Important: the platform is being updated"
EN_BODY = (
    "Dear user! We are strengthening security and adding new features on the Diamond Education platform. "
    "Because of this, some parts of the Student, Speaking and Teacher apps may not work fully or correctly until "
    "you update your app. Please update the app from the App Store or Google Play. We apologize for the "
    "inconvenience."
)

_MODULE: types.ModuleType | None = None


def _script() -> types.ModuleType:
    global _MODULE
    if _MODULE is None:
        spec = importlib.util.spec_from_file_location("send_platform_update_notice", SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE = module
    return _MODULE


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE")


class FakeDB:
    def __init__(self, mod: types.ModuleType) -> None:
        self.mod = mod
        self.users: list[dict[str, Any]] = []
        self.notices: list[dict[str, Any]] = []
        self.tokens: list[dict[str, Any]] = []
        self.speaking_devices: list[dict[str, Any]] = []
        self.speaking_records: list[dict[str, Any]] = []
        self.statements: list[str] = []
        self.transactions_first_statement: list[str] = []
        self.commits = 0
        self.lock_held = False

    def connect(self) -> "FakeConn":
        return FakeConn(self)


class FakeConn:
    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self.in_transaction = False
        self.read_only = False

    def cursor(self) -> "FakeCursor":
        return FakeCursor(self)

    def commit(self) -> None:
        self.db.commits += 1
        self.in_transaction = False
        self.read_only = False

    def rollback(self) -> None:
        self.in_transaction = False
        self.read_only = False

    def close(self) -> None:
        self.rollback()


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn
        self._rows: list[dict[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        db, mod = self.conn.db, self.conn.db.mod
        db.statements.append(sql)
        if not self.conn.in_transaction:
            self.conn.in_transaction = True
            db.transactions_first_statement.append(sql)
        if sql.strip().upper().startswith(WRITE_PREFIXES) and self.conn.read_only:
            raise RuntimeError("cannot execute a write in a read-only transaction")
        params = tuple(params or ())
        rows: list[dict[str, Any]]
        if sql == mod.READ_ONLY_SQL:
            self.conn.read_only = True
            rows = []
        elif sql == mod.LOCK_SQL:
            db.lock_held = True
            rows = [{"locked": True}]
        elif sql == mod.UNLOCK_SQL:
            db.lock_held = False
            rows = [{"unlocked": True}]
        elif sql == mod.ELIGIBLE_USERS_SQL:
            rows = [dict(user) for user in db.users]
        elif sql == mod.EXISTING_NOTICE_SQL:
            rows = [{"user_id": uid} for uid in sorted({n["user_id"] for n in db.notices if n["source_key"] == params[0]})]
        elif sql == mod.EXISTING_NOTICE_FOR_USERS_SQL:
            wanted = set(params[1])
            rows = [{"user_id": n["user_id"]} for n in db.notices if n["source_key"] == params[0] and n["user_id"] in wanted]
        elif sql == mod.INSERT_NOTICE_SQL:
            columns = (
                "user_id", "notification_type", "title", "message", "button_text",
                "button_url", "target_screen", "source_key", "meta_json",
            )
            row = dict(zip(columns, params), id=len(db.notices) + 1)
            db.notices.append(row)
            rows = [{"id": row["id"]}]
        elif sql == mod.USER_TOKENS_SQL:
            wanted = set(params[0])
            rows = [dict(token) for token in db.tokens if token["user_id"] in wanted]
        elif sql == mod.SPEAKING_RECORD_SQL:
            rows = [
                {k: r[k] for k in ("id", "status", "recipient_count")}
                for r in db.speaking_records
                if r["title"] == params[0] and r["body"] == params[1]
            ][:1]
        elif sql == mod.SPEAKING_DEVICES_SQL:
            rows = [dict(device) for device in db.speaking_devices]
        elif sql == mod.INSERT_SPEAKING_RECORD_SQL:
            record = {"id": 900 + len(db.speaking_records), "title": params[0], "body": params[1], "status": "sending", "recipient_count": 0}
            db.speaking_records.append(record)
            rows = [{"id": record["id"]}]
        elif sql == mod.UPDATE_SPEAKING_RECORD_SQL:
            for record in db.speaking_records:
                if record["id"] == params[2]:
                    record["recipient_count"], record["status"] = params[0], params[1]
            rows = []
        else:
            raise AssertionError(f"unexpected SQL: {sql.strip()[:80]}")
        self._rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


def _real_slot_for():
    """push_notifications._slot_for, executed alone (the module needs cryptography)."""
    source = (ROOT / "push_notifications.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_slot_for")
    namespace: dict[str, Any] = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "push_notifications.py", "exec"), namespace)
    return namespace["_slot_for"]


class FakeFirebase:
    """Fake firebase_admin.messaging plus the push_notifications surface the script uses."""

    def __init__(self, configured_slots: set[str]) -> None:
        self.configured_slots = configured_slots
        self.sent: list[tuple[str, Any]] = []
        self.pruned: list[str] = []
        self.unregistered_tokens: set[str] = set()
        self.init_calls = 0

        fake = self

        class _Box:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

        class UnregisteredError(Exception):
            code = "NOT_FOUND"

        class _Result:
            def __init__(self, success: bool, exception: Exception | None = None) -> None:
                self.success, self.exception = success, exception

        def send_each(messages: list[Any], app: Any = None) -> Any:
            results = []
            for message in messages:
                fake.sent.append((app, message))
                if message.token in fake.unregistered_tokens:
                    results.append(_Result(False, UnregisteredError("Requested entity was not found.")))
                else:
                    results.append(_Result(True))
            return _Box(responses=results)

        self.messaging = types.ModuleType("firebase_admin.messaging")
        for name in ("Message", "Notification", "AndroidConfig", "APNSConfig", "APNSPayload", "Aps"):
            setattr(self.messaging, name, type(name, (_Box,), {}))
        self.messaging.UnregisteredError = UnregisteredError
        self.messaging.send_each = send_each
        self.firebase_admin = types.ModuleType("firebase_admin")
        self.firebase_admin.messaging = self.messaging

        self.push_notifications = types.ModuleType("push_notifications")
        self.push_notifications._slot_for = _real_slot_for()
        self.push_notifications._firebase_apps = {slot: f"app:{slot}" for slot in configured_slots}

        def init_firebase() -> bool:
            fake.init_calls += 1
            return bool(configured_slots)

        self.push_notifications.init_firebase = init_firebase
        self.push_notifications._prune_tokens = lambda tokens: fake.pruned.extend(tokens)


def _token_encryption_module() -> types.ModuleType:
    module = types.ModuleType("token_encryption")

    class TokenEncryptionConfigurationError(RuntimeError):
        pass

    class TokenCipher:
        @classmethod
        def from_environment(cls) -> "TokenCipher":
            return cls()

        def decrypt(self, value: str) -> str:
            if value == "enc:v1:broken":
                raise ValueError("bad token")
            return value[len("enc:v1:"):] if value.startswith("enc:v1:") else value

    module.TokenCipher = TokenCipher
    module.TokenEncryptionConfigurationError = TokenEncryptionConfigurationError
    return module


@contextlib.contextmanager
def _fake_environment(db: FakeDB, firebase: FakeFirebase):
    db_module = types.ModuleType("db")
    db_module.get_conn = db.connect
    config_module = types.ModuleType("config")
    config_module.FIREBASE_CREDENTIALS_BY_SLOT = {slot: {"json": "{}"} for slot in firebase.configured_slots}
    fakes = {
        "db": db_module,
        "config": config_module,
        "push_notifications": firebase.push_notifications,
        "token_encryption": _token_encryption_module(),
        "firebase_admin": firebase.firebase_admin,
        "firebase_admin.messaging": firebase.messaging,
    }
    saved = {name: sys.modules.get(name) for name in fakes}
    sys.modules.update(fakes)
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _run(mod: types.ModuleType, argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = mod.main(argv)
    return code, out.getvalue()


def _populated_db(mod: types.ModuleType) -> FakeDB:
    db = FakeDB(mod)
    db.users = [
        {"id": 1, "login_id": "S-1", "login_type": 2, "language": "uz"},
        {"id": 2, "login_id": "T-2", "login_type": 3, "language": "ru"},
        {"id": 3, "login_id": "MEDIA-X-01", "login_type": 4, "language": "en"},
        {"id": 4, "login_id": "S-4", "login_type": 1, "language": None},
        {"id": 5, "login_id": "SP-5", "login_type": 7, "language": "en"},
    ]
    # User 4 already received the notice in an earlier run.
    db.notices = [{"id": 1, "user_id": 4, "source_key": mod.SOURCE_KEY}]
    db.tokens = [
        {"user_id": 1, "token": "tok-student-android", "app": "student", "platform": "android"},
        {"user_id": 1, "token": "tok-student-dead", "app": "student", "platform": "android"},
        {"user_id": 2, "token": "tok-teacher-ios", "app": "teacher", "platform": "ios"},
        {"user_id": 3, "token": "tok-media-web", "app": "teacher", "platform": "web"},
        {"user_id": 4, "token": "tok-already-has-it", "app": "student", "platform": "android"},
    ]
    db.speaking_devices = [
        {"device_row_id": 1, "token": "enc:v1:sp-anon", "platform": "android", "user_id": None, "account_id": None},
        {"device_row_id": 2, "token": "enc:v1:sp-ru", "platform": "ios", "user_id": 5, "account_id": 5,
         "language": "ru", "blocked": 0, "active": 1, "screenshot_demo": 0, "speaking_deleted_at": None},
        {"device_row_id": 3, "token": "enc:v1:sp-blocked", "platform": "android", "user_id": 6, "account_id": 6,
         "language": "uz", "blocked": 1, "active": 1, "screenshot_demo": 0, "speaking_deleted_at": None},
        {"device_row_id": 4, "token": "enc:v1:broken", "platform": "android", "user_id": None, "account_id": None},
    ]
    return db


ALL_SLOTS = {"STUDENT_ANDROID", "STUDENT_IOS", "TEACHER_ANDROID", "TEACHER_IOS", "SPEAKING_ANDROID", "SPEAKING_IOS"}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_script_parses_and_avoids_main_and_telegram():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    assert not {name for name in imported if name.startswith("backend")}, "the script must not import backend/main.py"
    assert {"db", "config", "push_notifications"} <= imported
    lowered = source.lower()
    assert "api.telegram.org" not in lowered and "_send_telegram" not in lowered and "sendmessage" not in lowered


def test_texts_are_exact_trilingual_and_fit_limits():
    mod = _script()
    assert mod.PUSH_TEXTS == {
        "uz": {"title": UZ_TITLE, "body": UZ_BODY},
        "ru": {"title": RU_TITLE, "body": RU_BODY},
        "en": {"title": EN_TITLE, "body": EN_BODY},
    }
    assert mod.LANGUAGES == ("uz", "ru", "en") and mod.DEFAULT_LANGUAGE == "uz"
    assert mod.INBOX_TITLE == "Muhim · Важно · Important"
    assert mod.INBOX_MESSAGE == f"{UZ_BODY}\n\n{RU_BODY}\n\n{EN_BODY}"
    assert mod.INBOX_MESSAGE.index(UZ_BODY) < mod.INBOX_MESSAGE.index(RU_BODY) < mod.INBOX_MESSAGE.index(EN_BODY)
    assert any("\u0400" <= ch <= "\u04ff" for ch in RU_BODY)
    # backend/_payment_upsert_web_notification caps title at 180 and message at 2000.
    assert len(mod.INBOX_TITLE) <= 180 and len(mod.INBOX_MESSAGE) <= 2000
    for text in mod.PUSH_TEXTS.values():
        assert len(text["title"]) <= mod.PUSH_TITLE_LIMIT and len(text["body"]) <= mod.PUSH_BODY_LIMIT
        # FCM payload limit is 4096 bytes: notification + the trilingual data.
        payload = {"notification": text, "data": mod.speaking_push_data(1)}
        assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) < 4000


def test_idempotency_key_popup_type_and_push_data():
    mod = _script()
    assert mod.SOURCE_KEY == "platform_update_notice_2026_10_28"
    assert mod.NOTIFICATION_TYPE == "broadcast"  # the type the website and both apps pop up
    assert "source_key" in mod.INSERT_NOTICE_SQL and "notification_type" in mod.INSERT_NOTICE_SQL
    assert "source_key = ?" in mod.EXISTING_NOTICE_SQL and "source_key = ?" in mod.EXISTING_NOTICE_FOR_USERS_SQL
    # Same push data as an admin broadcast (backend/main.py _run_broadcast_job).
    backend = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    job = backend.split("async def _run_broadcast_job(", 1)[1].split("\nasync def ", 1)[0].split("\ndef ", 1)[0]
    data_literal = job.split('kwargs={"data": ', 1)[1].split("},\n", 1)[0]
    admin_keys = dict(ast.literal_eval(data_literal.replace("str(button_url or \"\")", '""')))
    assert mod.APP_PUSH_DATA == admin_keys == {"target_screen": "notifications", "button_url": "", "notification_type": "broadcast"}
    # Speaking popups are driven by the Speaking admin announcement type.
    assert '"type": "speaking_announcement"' in (ROOT / "backend" / "speaking_admin.py").read_text(encoding="utf-8")
    assert mod.SPEAKING_PUSH_TYPE == "speaking_announcement"
    data = mod.speaking_push_data(7)
    assert data["type"] == "speaking_announcement" and data["notification_id"] == "7"
    assert data["title"] == mod.INBOX_TITLE and data["body"] == mod.INBOX_MESSAGE
    # Active, non-blocked, real accounts only.
    for clause in ("COALESCE(blocked, 0) = 0", "COALESCE(active, 1) = 1", "COALESCE(screenshot_demo, 0) = 0", "speaking_deleted_at IS NULL"):
        assert clause in mod.ELIGIBLE_USERS_SQL


def test_mode_flags_default_to_dry_run():
    mod = _script()
    assert mod.parse_args([]).send is False
    assert mod.parse_args(["--dry-run"]).send is False
    assert mod.parse_args(["--send"]).send is True
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            mod.parse_args(["--send", "--dry-run"])
        except SystemExit:
            pass
        else:
            raise AssertionError("--send and --dry-run must be mutually exclusive")


def test_dry_run_is_default_and_writes_nothing():
    mod = _script()
    for argv in ([], ["--dry-run"]):
        db = _populated_db(mod)
        firebase = FakeFirebase(ALL_SLOTS)
        notices_before = [dict(n) for n in db.notices]
        with _fake_environment(db, firebase):
            code, out = _run(mod, argv)
        assert code == 0
        assert not [s for s in db.statements if s.strip().upper().startswith(WRITE_PREFIXES)]
        assert "pg_try_advisory_lock" not in " ".join(db.statements)
        assert db.transactions_first_statement and all(s == mod.READ_ONLY_SQL for s in db.transactions_first_statement)
        assert db.commits == 0 and db.notices == notices_before and not db.speaking_records
        assert firebase.init_calls == 0 and not firebase.sent and not firebase.pruned
        assert "DRY RUN" in out and "would create: 4" in out and "already have the notice: 1" in out
        assert "Nothing was written" in out


def test_send_creates_missing_items_pushes_once_and_is_idempotent():
    mod = _script()
    db = _populated_db(mod)
    firebase = FakeFirebase(ALL_SLOTS)
    firebase.unregistered_tokens = {"tok-student-dead"}
    with _fake_environment(db, firebase):
        code, out = _run(mod, ["--send"])
    assert code == 0, out
    assert not db.lock_held, "advisory lock must be released"

    created = {n["user_id"]: n for n in db.notices if n["id"] != 1}
    assert sorted(created) == [1, 2, 3, 5]  # user 4 already had it
    for row in created.values():
        assert row["notification_type"] == "broadcast" and row["source_key"] == mod.SOURCE_KEY
        assert row["title"] == mod.INBOX_TITLE and row["message"] == mod.INBOX_MESSAGE
        assert (row["button_url"], row["target_screen"]) == ("/?section=home", "home")

    app_pushes = [m for app, m in firebase.sent if not str(app).startswith("app:SPEAKING")]
    by_token = {m.token: m for m in app_pushes}
    # Web tokens have no FCM project; the user who already had the item gets nothing.
    assert set(by_token) == {"tok-student-android", "tok-student-dead", "tok-teacher-ios"}
    assert by_token["tok-student-android"].notification.title == UZ_TITLE
    assert by_token["tok-student-android"].notification.body == UZ_BODY
    assert by_token["tok-teacher-ios"].notification.title == RU_TITLE
    assert by_token["tok-teacher-ios"].data == mod.APP_PUSH_DATA
    assert firebase.pruned == ["tok-student-dead"]

    speaking = [m for app, m in firebase.sent if str(app).startswith("app:SPEAKING")]
    assert {m.token for m in speaking} == {"sp-anon", "sp-ru"}  # blocked account and unreadable token skipped
    titles = {m.token: m.notification.title for m in speaking}
    assert titles == {"sp-anon": UZ_TITLE, "sp-ru": RU_TITLE}
    for message in speaking:
        assert message.data["type"] == "speaking_announcement"
        assert message.data["title"] == mod.INBOX_TITLE and message.data["body"] == mod.INBOX_MESSAGE
    assert len(db.speaking_records) == 1
    record = db.speaking_records[0]
    assert record["status"] == "sent" and record["recipient_count"] == 2
    assert all(m.data["notification_id"] == str(record["id"]) for m in speaking)

    # A second run finds every item and the Speaking record: nothing new.
    sent_before, notices_before = len(firebase.sent), len(db.notices)
    with _fake_environment(db, firebase):
        code, out = _run(mod, ["--send"])
    assert code == 0, out
    assert len(db.notices) == notices_before and len(firebase.sent) == sent_before
    assert len(db.speaking_records) == 1
    assert "already sent" in out


def test_send_aborts_before_writing_without_firebase():
    mod = _script()
    db = _populated_db(mod)
    firebase = FakeFirebase(set())
    with _fake_environment(db, firebase):
        code, out = _run(mod, ["--send"])
    assert code == 2 and "nothing was written" in out
    assert len(db.notices) == 1 and not db.speaking_records and not firebase.sent
    assert not db.lock_held


if __name__ == "__main__":
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
