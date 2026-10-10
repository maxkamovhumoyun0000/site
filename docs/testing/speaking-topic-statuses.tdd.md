# Speaking topic-status choices

Source: user request derived during this TDD run.

User journeys:

- A media administrator can set a Speaking topic to `COMMON`, `PREDICTED`,
  or `HIGH FREQUENCY`, and the API rejects any other value.
- AI independently chooses one of those canonical values when it generates a
  topic. `PREDICTED` is shown to users as `PREDICTED TILL THE END OF 2026`.

| Guarantee | Test | Result |
| --- | --- | --- |
| Supported status values are normalized | `test_normalizes_supported_topic_statuses` | RED, then PASS |
| Unsupported status values are rejected | `test_rejects_unknown_topic_statuses` | RED, then PASS |
| A predicted value gets its end-of-2026 user-facing label while the other values remain unchanged | `test_displays_predicted_status_with_its_2026_validity` | RED, then PASS |

RED evidence: `python3 -m unittest tests/test_speaking_topic_status_contract.py`
failed because `display_topic_status` did not exist. GREEN evidence:
`python3 -m unittest discover -s tests -p 'test_speaking_*.py' -v` passed all
12 tests. The local checkout has no `node_modules`, so frontend compilation is
validated by the production deployment build rather than a local build.
