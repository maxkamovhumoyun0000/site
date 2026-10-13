# PostgreSQL Speaking verification expiry TDD evidence

## User journey

A fresh email verification code remains valid when the production PostgreSQL
driver returns its expiry column as a timezone-aware `datetime`.

## RED

Commit `4aa9afa` added a test for a future PostgreSQL `datetime`. It failed
because no type-safe expiry helper existed; the endpoint used lexicographic
string comparison.

## GREEN

Commit `6825e49` parses database timestamp values and compares instants in
UTC. `python3 -m unittest tests.test_speaking_token_security` and
`python3 -m py_compile backend/main.py speaking_contract.py` passed.
