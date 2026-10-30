# Arena and safety-report verification

The user journeys were derived from the request: reports must appear in the
main-admin feedback inbox; Arena/Duel participants wait for active opponents;
and matches may use unseen, suitable bank questions to reduce startup delay.

| Guarantee | Evidence | Result and limits |
| --- | --- | --- |
| A report and its inbox copy commit together; duplicate submissions do not duplicate messages and can repair a missing copy. | `python3 tests/test_safety_report_delivery.py` | Three isolated SQLite tests pass. The initial test failed because the atomic delivery argument was absent; a later test failed because a closed thread remained closed. PostgreSQL and notifications were not integration-tested. |
| Suitable fast-start bank candidates exclude previously seen and duplicate questions and other levels. | `python3 tests/test_arena_fast_questions.py` | One isolated selector test passes; initial test failed because the selector did not exist. It does not establish that a production bank has sufficient questions. |
| Round barriers, offline exclusion and rejoin helper behavior. | `python3 tests/test_arena_runtime_contracts.py` | 23 stdlib tests pass, including isolated helper tests; no multi-worker database or device end-to-end test was run. |

Coverage was not measured. Flutter, multi-device and full API/database
integration tests remain necessary; the local machine has no attached Android
device and the local Python environment lacks FastAPI. No local build was run.
