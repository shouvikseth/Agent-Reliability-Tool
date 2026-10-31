# Four-week implementation plan

## Week 1 — target and validation (12–15 hours)

Implemented: original FastAPI/SQLite issue tracker, eight development mutations, author-only verifier construction, public regression test, seed/reference validation, and runtime tests.

Next: strengthen regression coverage, add concurrent duplicate-request semantics or explicitly exclude concurrency, and document each task's intended behavior. Acceptance: every broken task fails only its intended defect checks and every reference patch passes all checks.

## Week 2 — isolated real-model execution (15–18 hours)

Implemented foundation: shared model protocol, three role/control-flow contracts, narrow file tools, single-shot timeout/malformed response injection, aggregate usage accounting, terminal submission, diffs, JSONL events, and SQLite persistence.

Docker milestone implemented: restricted disposable containers, bounded source transfer, external API grading with no hidden tests inside containers, image-ID recording, candidate deadlines, cleanup, and infrastructure-error propagation. Integration checks cover restrictions, outbound network denial, read-only root, broken/fixed grading, public tests, and hanging candidates.

Provider milestone implemented: optional pinned OpenAI SDK; Responses function-call adapter; pinned pilot model/rates; exact input-token preflight; pre-call token/dollar reservation; automatic retries disabled; shared role ledger; request deadline cancellation; uncertain billing retained explicitly; mocked SDK and Docker repair tests; live-model CLI restricted to Docker. Live API behavior and account model access still require a user-run pilot with credentials.

Remaining: paid pilot evidence, reconciliation against provider billing, broader adversarial hardening and infrastructure error classification, full prompt/provenance freeze. Acceptance: hostile candidate and path-escape tests cannot reach host files or author assets, timeouts stop child processes, and role/retry costs reconcile.

## Week 3 — freeze and evaluation (12–17 hours)

Development pilots and the selected configuration are documented. Twelve new held-out defects across four categories now pass mechanical Docker validation, with seeded/reference source and test hashes, selected provider settings, and 216 balanced design slots recorded in [the held-out design](HELDOUT_DESIGN.md). No held-out model trials have run. The author-only design uses stable slot IDs; the historical CLI schedule remains a placeholder. Next add append-only execution attempts, exclusion records, interruption reconciliation, resume behavior, and live environment/model preflight, then freeze the runnable study manifest.

Acceptance: 216 scheduled outcomes accounted for, exclusions and reruns auditable, no tuning from inspected held-out outcomes. Actual model evaluation needs a configured provider, shared resource limits, working isolation, and matching fingerprints. The selected local Ollama provider requires no paid API credentials; paid provider evaluation would require a separate explicit spend budget.

## Week 4 — reporting and trace viewer (11–15 hours)

Build a small read-only results API and Next.js viewer from persisted runs: issue, visible model text, tool calls, injection events, patch, verification, and resource usage. Add a separate disposable patch-review checkout only after read-only viewing works.

Report raw counts and percentages, per-task consistency, fault assignment versus triggering, median/range durations including failures, regression rate, budget exhaustion, and cost per verified success (null when none succeed). Keep scripted runs out of research tables. Any interval must resample tasks rather than runs. Publish reproduction commands, frozen manifest, limitations, raw results, and a short negative-result-friendly narrative.
