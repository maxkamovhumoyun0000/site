# Speaking batch topic generation

Source: user request derived during this TDD run.

User journey: A media administrator can generate multiple distinct Speaking
topics and their questions, review the batch, and save all of it in one action.

| Guarantee | Test | Result |
| --- | --- | --- |
| A batch allows one through five topics | `test_allows_a_safe_batch_of_topics` | RED, then PASS |
| Invalid batch sizes are rejected | `test_rejects_out_of_range_or_invalid_topic_counts` | RED, then PASS |

RED evidence: `python3 -m unittest tests/test_speaking_batch_contract.py`
failed because the batch-count validator did not exist. GREEN evidence:
`python3 -m unittest tests/test_speaking_batch_contract.py tests/test_speaking_question_contract.py tests/test_speaking_topic_status_contract.py tests/test_speaking_token_security.py`
passed all eleven tests. The production Next.js build will provide the
TypeScript validation because this local checkout has no `node_modules`.
