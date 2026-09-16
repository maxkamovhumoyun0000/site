# Personalization TDD evidence

Source: the approved Personalization, Study-room and Parent Progress plan supplied in this task.

| Guarantee | Test / validation | Result |
|---|---|---|
| Parent progress links are opaque, not a student login ID | `tests/test_personalization_contracts.py::test_parent_access_token_is_opaque_and_not_login_id` | RED: helper absent; GREEN: passed |
| Study-room invite code is exactly six digits | `tests/test_personalization_contracts.py::test_study_room_code_has_exactly_six_digits` | RED: helper absent; GREEN: passed |
| Correct mistake reviews increase the spaced-review interval | `tests/test_personalization_contracts.py::test_mistake_review_spacing_grows_after_correct_answers` | RED: helper absent; GREEN: passed |
| Website additions type-check and lint | `npm run lint`, `npm run build` | Passed |
| Backend compiles | `python3 -m py_compile backend/main.py backend/personalization.py` | Passed |

The three contract tests were executed with the production-compatible server venv:

```text
PYTHONPATH=. .venv/bin/pytest -q tests/test_personalization_contracts.py
3 passed
```

Known follow-up: the final visual certificate template and custom badge artwork are intentionally data-driven and await the design files supplied by the product owner. The existing branded fallback and verification data contracts do not depend on those assets.
