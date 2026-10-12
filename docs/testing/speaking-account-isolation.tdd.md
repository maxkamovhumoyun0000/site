# Speaking account isolation and VoiceRoom access — TDD evidence

## Scope

Diamond Speaking registration creates a dedicated, immediately active account.
It is not a general Student/Teacher public-registration request, so it is
excluded from the normal administrator user directory and appears only in the
separate **Speaking App foydalanuvchilari** view.

## RED checkpoint

Commit `7cf3a9b` added the VoiceRoom identity contract reproducer before the
supporting Speaking account contract functions existed. The test failed at
import/lookup time as expected.

## GREEN evidence

Run from the repository root:

```text
python3 -m unittest tests.test_speaking_question_contract -v
python3 -m py_compile backend/main.py speaking_contract.py
```

Result: **16 contract tests passed** and both server modules compiled.

The verified contract covers the dedicated account marker parser, display-safe
VoiceRoom fallback identity, and existing Speaking request safety rules. The
endpoint enforces a distinct `speaking_app_account=1` marker, immediately
issues a normal bearer session only after an emailed, single-use six-digit
code is verified. It soft-deactivates a standalone Speaking account, retains
its historical row for the dedicated admin list, and restores that account
only when the original contact email is verified again.

The same contract validates the canonical `SPEAK-XXXXXXXX` Student-App link
code and the three-device replacement rule. A link code does not contain an
account identity: an already signed-in Student App session must approve it
before Diamond Speaking receives a normal bearer session.

## UI verification boundary

The Next.js lint command could not run locally because this checkout has no
`node_modules` (`eslint: not found`). No frontend build was run. The component
uses the existing authenticated `apiFetch` contract and its route is present in
the admin navigation configuration; deployment should run the repository's
normal frontend dependency/install and build steps.
