# Mobile scheduled maintenance — TDD evidence

## Source and journeys

No separate plan was supplied; the journeys were derived from the request.

- As the Developer account, I can turn Student and Teacher maintenance on or
  off and set a start, end, and Uzbek message.
- As a mobile user, I see the maintenance screen only while the enabled window
  is active, including its expected completion time.
- As a regular admin or Media account, I cannot use the server-monitoring or
  mobile-maintenance API.

## RED and GREEN checkpoints

- RED commit: `5af121c test: cover scheduled mobile maintenance`.
  The pre-implementation test run executed five app-version tests and failed
  the two new tests because `_maintenance_state` and maintenance fields did not
  exist.
- GREEN validation: `PYTHONPATH=/tmp/diamond-maintenance-test:/root/diamond-site
  /root/diamond-site/.venv/bin/python -m pytest /tmp/test_app_version_controls.py`
  completed with `7 passed` against an isolated copy of the final backend.

| # | Guarantee | Test / command | Type | Result |
|---|---|---|---|---|
| 1 | Maintenance is active only inside its enabled time window. | `tests/test_app_version_controls.py::test_maintenance_window_is_active_only_inside_its_configured_interval` | Unit | PASS |
| 2 | Per-app maintenance fields are normalized safely. | `tests/test_app_version_controls.py::test_maintenance_settings_payload_accepts_only_safe_app_specific_fields` | Unit | PASS |
| 3 | An end time before (or equal to) start is rejected. | `tests/test_app_version_controls.py::test_maintenance_window_rejects_an_end_before_its_start` | Unit | PASS |
| 4 | Developer-only identity excludes the Media account. | `tests/test_app_version_controls.py::test_developer_scope_is_limited_to_the_dedicated_login` | Unit | PASS |
| 5 | Existing server monitoring and payment receipt regressions remain covered. | `tests/test_system_metrics.py`, `tests/test_payment_receipts.py` | Unit/integration | Previously green; re-run after production sync |
| 6 | Both mobile projects compile and their suites remain green. | `flutter analyze && flutter test` in Student and Teacher repositories | Static/unit/widget | PASS: Student 15; Teacher 18 |

## Coverage and known gaps

This repository does not expose a configured Python coverage command in the
local workspace (the local Python interpreter has no `pytest`). The targeted
backend suite was run in the server virtual environment against an isolated
final-code copy. The production deploy re-runs the backend regression set.

Browser E2E and store-device tests are intentionally not automated here: the
Developer UI requires a real restricted credential, and maintenance behavior
on existing devices requires release builds of the two mobile apps. The app
providers re-check on launch, foreground, every 15 minutes, and exactly after
the nearest scheduled boundary.
