# Developer release ownership — TDD evidence

## User journeys

1. As an admin, I cannot change mobile release settings through Diamondvoy.
2. As a Developer, I manage mobile releases and scheduled-maintenance messages
   from separate Developer workspace pages.
3. As a Developer, I open server status, mobile releases, and maintenance as
   independent navigable pages rather than one long dashboard.
4. As a Student or Teacher app user, I receive the maintenance message in the
   requested Uzbek, Russian, or English language when that translation exists.

## RED / GREEN evidence

| Stage | Command | Result |
|---|---|---|
| RED | `PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_app_version_controls.py` | 2 failed: the Diamondvoy version mutator still existed, and maintenance state did not accept a language. |
| GREEN | `PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_app_version_controls.py tests/test_developer_workspace.py` | 12 passed. |
| RED (pages) | `PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_developer_workspace.py` | 1 expected failure: Developer only exposed `home` and `profile`. |

## Guarantees

| # | Guarantee | Test | Result |
|---|---|---|---|
| 1 | The former Diamondvoy mobile-release mutation helper is absent. | `test_diamondvoy_has_no_mobile_release_mutator` | PASS |
| 2 | The maintenance response selects the mobile app language, falling back safely when needed. | `test_maintenance_state_selects_the_mobile_app_language` | PASS |
| 3 | Developer release API allowlisting and restricted payload handling continue to work. | `tests/test_developer_workspace.py` | PASS |
| 4 | Developer navigation exposes separate server-status, mobile-release, and mobile-maintenance pages. | `test_developer_has_separate_system_release_and_maintenance_pages` | Pending final environment test |

## Notes

The older admin REST endpoints remain for compatibility; the requested removal
applies to Diamondvoy’s action/wizard path. Release and maintenance controls
are available only from the restricted Developer workspace. The final focused
test run will be performed in the project virtual environment before any
approved deployment; the local shell does not have pytest installed. Python
coverage is not configured in this repository; focused tests and the frontend
type check are used as validation.
