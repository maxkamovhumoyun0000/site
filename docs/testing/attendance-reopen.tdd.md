# Attendance reopen — TDD evidence

Source: user request on 2026-10-14.

## User journeys

1. An authorized teacher or admin can update attendance for a selected old lesson date while a developer has opened that finite date range.
2. A developer can configure the start date, end date, and automatic closing time, or immediately close the window.
3. A cancelled lesson or a student who was not in the group on that date remains ineligible.

## RED / GREEN

- RED: `python3 -c "...test_attendance_temporary_reopen_is_scoped_and_expires()"` failed because the scoped reopen configuration did not exist.
- GREEN: the same contract runner passed after the server timing override and client affordance were added.
- RED: `python3 -c "...test_developer_can_manage_a_finite_attendance_reopen_window()"` failed because no developer-managed endpoint or workspace existed.
- GREEN: both contract files passed after the persisted developer controls were added.

## Guarantees

| Guarantee | Evidence | Result |
|---|---|---|
| Reopen range is finite and only includes configured dates | `tests/test_attendance_temporary_reopen_contract.py` | PASS |
| Disabled setting closes the exception immediately | same helper test | PASS |
| Developer-only read/write API and workspace route exist | `tests/test_developer_attendance_reopen_contract.py` | PASS |
| Python sources compile | `python3 -m py_compile backend/main.py db.py` | PASS |

`pytest` is not installed in this local environment, so the two dependency-free contract files were run directly through `importlib`; no coverage tool is configured for this repository.
