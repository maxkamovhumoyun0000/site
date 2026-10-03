# Developer workspace — TDD evidence

## Source and user journeys

No plan document was supplied. The work was derived from the request to expand
the Developer account while preserving role separation, i18n, and both themes.

1. As the dedicated Developer, I can set the Student and Teacher mobile release
   version, build number, and official store links without gaining ordinary
   admin access.
2. As the dedicated Developer, I can inspect privacy-safe server capacity,
   recent aggregate load history, and actionable guidance in my chosen language.
3. As an operator, I can retain the existing scheduled mobile-maintenance
   control without a release update accidentally changing its settings.

## RED / GREEN evidence

| Stage | Command | Result |
|---|---|---|
| RED | `PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_developer_workspace.py` | 2 failed: the release route was absent from the Developer allowlist and the restricted release normalizer did not exist. |
| GREEN | `PYTHONPATH=/root/diamond-site .venv/bin/pytest -q tests/test_developer_workspace.py tests/test_app_version_controls.py` | 11 passed. |

## Guarantees

| # | What is guaranteed | Test | Type | Result |
|---|---|---|---|---|
| 1 | The dedicated Developer path allowlist includes the mobile-release endpoint. | `test_developer_workspace_allows_only_its_mobile_release_endpoint` | Unit/security boundary | PASS |
| 2 | A Developer release payload maps versions, builds, and store URLs but excludes maintenance fields. | `test_developer_release_payload_keeps_maintenance_settings_out` | Unit | PASS |
| 3 | Existing version, maintenance-window, Developer-role, and deny-by-default route checks remain intact. | `tests/test_app_version_controls.py` | Regression | PASS |

## Coverage and known gaps

The repository has no configured Python coverage command. The focused backend
tests are green; the production frontend build remains the integration/type
check for the client workspace. Visual browser testing of both themes is a
manual follow-up after deploy, because the authenticated Developer flow has no
Playwright fixture in this repository.
