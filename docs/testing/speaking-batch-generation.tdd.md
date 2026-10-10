# Resilient Speaking batch generation

Source: user-reported production error during AI topic generation.

User journey: A media administrator can generate several Speaking topics at
once without one oversized AI response being truncated and rejected as a
request error.

| Guarantee | Test | Result |
| --- | --- | --- |
| One topic uses the normal one-response path | `test_splits_multi_topic_requests_into_individual_ai_generations` | RED, then PASS |
| A 2–5 topic batch is split into one AI generation per topic | `test_splits_multi_topic_requests_into_individual_ai_generations` | RED, then PASS |

RED evidence: `python3 -m unittest tests/test_speaking_batch_generation.py -v`
failed because `individual_ai_topic_generation_count` did not exist. GREEN
evidence: `python3 -m unittest discover -s tests -p 'test_speaking_*.py' -v`
passed 13 tests. Production logs identified the root cause as truncated AI
batch content (`Batch topic … must contain 10 questions`), not a database
failure.
