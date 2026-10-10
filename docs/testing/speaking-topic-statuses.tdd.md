# Speaking topic-status choices

Source: user request derived during this TDD run.

User journey: A media administrator can set a Speaking topic to `COMMON`,
`PREDICTED`, or `HIGH FREQUENCY`, and the API rejects any other value.

| Guarantee | Test | Result |
| --- | --- | --- |
| Supported status values are normalized | `test_normalizes_supported_topic_statuses` | RED, then PASS |
| Unsupported status values are rejected | `test_rejects_unknown_topic_statuses` | RED, then PASS |

RED evidence: `python3 -m unittest tests/test_speaking_topic_status_contract.py`
failed because the normalizer did not exist. GREEN evidence:
`python3 -m unittest tests/test_speaking_topic_status_contract.py tests/test_speaking_question_contract.py tests/test_speaking_token_security.py`
passed all eight tests. The focused frontend lint command could not run because
the local checkout has no `node_modules`; no build was run.
