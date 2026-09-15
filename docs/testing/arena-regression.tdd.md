# Arena runtime regression evidence

Source: user-reported Arena/Duel behaviour, derived during this TDD run.

| # | Guarantee | Test | Result |
|---|---|---|---|
| 1 | A student receives their own next question immediately after answering, rather than waiting for an opponent between questions. | `tests/test_competition_question_progression.py::test_answer_response_contains_the_next_question_without_waiting_for_opponent` | PASS |
| 2 | Malformed questions, duplicate choices, and out-of-range correct answers are rejected before an Arena/Duel starts. | `test_competition_question_validator_rejects_malformed_or_ambiguous_rows` | PASS |
| 3 | A repeated prompt is rejected even if its distractor choices differ. | `test_competition_question_deduplication_uses_the_question_not_distractors` | PASS |
| 4 | A valid database `time_limit_sec` is returned as the Arena/Duel question timer. | `test_competition_timer_uses_the_database_question_limit_with_safe_bounds` | PASS |

RED evidence:

- The missing validity filter raised `AttributeError` on the new validator test.
- The duplicate-prompt test raised `AssertionError` before the question key was corrected.
- The database-duration test returned the old 40 seconds instead of the stored 47 seconds.

GREEN evidence:

```text
PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_competition_question_progression.py
4 passed
```

Coverage note: this repository has no configured Python coverage command in the checked runtime. The targeted unit suite above covers the changed decision paths; full-suite coverage remains a follow-up.
