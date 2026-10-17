# AeroGuard Agent Rules

Before changing code, read in order: `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/OWNERSHIP.md`, `docs/INTEGRATION.md`, then your assignment in `docs/TEAM_HANDOFF.md`.

1. Modify only your owned implementation paths and owned tests. Do not edit another owner's files without explicit approval.
2. Treat canonical Pydantic models, public interfaces, endpoint schemas, and generated OpenAPI/JSON Schema/TypeScript files as frozen contract v1 after bootstrap.
3. Never edit generated artifacts manually; run the approved generator. Only Abhinav edits canonical contracts after Rupesh approves an architectural change.
4. Do not create a second API server, event schema, state enum, database, composition root, or direct feature-to-feature internal import. The orchestrator alone wires modules, dispatches events, and orders persistence.
5. Guardian never controls the simulator. Sentinel may request only enumerated symbolic actions after current-run authorization; the simulator validates independently. Never use LLM output for action approval.
6. Preserve safety invariants: camera obstruction is `UNKNOWN`; one responsive pilot blocks dual-incapacity claims; ATC disconnection alone cannot authorize fallback; stale, mismatched, rejected, or replayed commands cannot execute actions.
7. Use typed boundaries, maintainable type hints, stable scenario IDs, injected virtual time, deterministic tests, negative tests, and regression tests. Keep mock/no-webcam/no-IBM mode working.
8. If a contract blocks work, write a minimal change request under the process in `docs/CONTRACT_CHANGE_PROTOCOL.md`; never invent local JSON fields or signatures.
9. Before a PR, run all applicable tests, contract drift checks, and smoke checks. Report exact commands, results, limitations, and blockers; never claim an unexecuted check passed.
10. Follow branch ownership. Never push directly to `main`, force-push shared refs, commit secrets, rewrite history, perform destructive Git operations, publish a repository, deploy, or modify remote resources without authorization.
11. Mark every UI and public-facing document: **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**. No real aircraft data, avionics, ATC integration, flight guidance, or operational navigation code is allowed.
12. For coding and DSA explanations, use only plain Markdown, standard fenced code blocks, normal Markdown tables, and plain-text trees. Do not emit HTML, XML, JSX explanations, custom components, interactive UI, or quizzes.
