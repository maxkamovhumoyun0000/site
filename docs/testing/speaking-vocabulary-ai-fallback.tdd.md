# TDD evidence: Speaking vocabulary AI fallback

## Scope

The public Speaking vocabulary endpoint searches the shared vocabulary bank
for English or Russian. A safe missing word can be prepared by the existing
vocabulary AI path; unsafe requests are rejected before any lookup or AI call.

## RED

Contract tests for normal and unsafe English/Russian vocabulary queries were
added before `is_safe_speaking_vocabulary_query` existed. The focused test run
failed with the missing import as expected.

## GREEN verification

```text
python3 -m unittest tests.test_speaking_question_contract tests.test_speaking_batch_generation
Ran 11 tests ... OK
```

## Guardrails

Unsafe terms are never passed to the AI path. Missing-word generation is also
rate limited per installation, and shared entries are reused for later users.

Coverage percentage was not measured; the focused contract and batch tests
above are the regression gate.
