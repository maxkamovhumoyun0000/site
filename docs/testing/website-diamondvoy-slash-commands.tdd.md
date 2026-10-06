# Website Diamondvoy slash commands — TDD evidence

Source: user journey derived during this task; no plan file was supplied.

| # | Guaranteed behavior | Test / command | Result |
|---|---|---|---|
| 1 | `/oquvchi-qoshish` and `/add-students` map to the existing-chat student-import action. | `node --test tests/diamondvoy-admin-commands.test.js` | PASS — 2 tests passed. |
| 2 | The action suggestion is only eligible after the administrator enters `/`; ordinary text does not trigger it. | Same unit test | PASS. |

RED evidence: before the helper existed, the test failed with
`Cannot find module '../app/ui/diamondvoy-admin-commands'`.

GREEN evidence: the same test passed after implementation. The focused Node
coverage run reported 100% line and function coverage for the command helper.

Static validation: `npm run lint` was run. It still fails because
`app/ui/universal-chat.tsx` already has 27 unrelated errors (React effect and
unescaped-entity rules); the new command helper and the newly added UI lines
produced no lint diagnostics. No local Next.js build was run.
