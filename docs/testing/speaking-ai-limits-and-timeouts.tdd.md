# Speaking AI limits and timeouts — TDD record

## Requirement

The media Speaking generator must accept up to ten questions, allow two to five
topics in a batch, and return a bounded error rather than leaving Russian
generation waiting indefinitely.

## Red

`tests/test_speaking_batch_contract.py::test_accepts_up_to_ten_questions_for_ai_generation`
was added before `normalize_question_generation_count` existed. The test
initially failed at import time.

## Green

The shared contract now validates counts from 1 through 10. The admin API uses
that contract and wraps primary/fallback provider calls with 90/60-second
deadlines. The media UI starts count inputs blank, validates the same ranges,
shows their maximums, and keeps a client timeout long enough for batch work.

## Verification

`python3 -m unittest discover -s tests -p 'test_speaking_*.py' -v` — 14 passing.
