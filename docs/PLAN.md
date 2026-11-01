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

Development pilots, the selected configuration, and the separately validated twelve-task catalog are documented. The [study runner](STUDY_RUNNER.md) records durable append-only attempts, reconciles interruptions, resumes only unstarted slots, prevents concurrent runners, and freezes/checks runtime and environment fingerprints. The [216-trial frozen evaluation](HELDOUT_EVALUATION.md) is complete: fixed 63/72, single 12/72, team 36/72 verified. All scheduled outcomes remain in the denominator; there were no exclusions, replacement attempts, infrastructure failures, or interruptions. Six single-agent usage records retain uncertainty. All 109 tests pass. Keep the historical CLI schedule as a placeholder and preserve the completed study rather than retuning on its outcomes.

Acceptance: 216 scheduled outcomes accounted for, exclusions and reruns auditable, no tuning from inspected held-out outcomes. Actual model evaluation needs a configured provider, shared resource limits, working isolation, and matching fingerprints. The selected local Ollama provider requires no paid API credentials; paid provider evaluation would require a separate explicit spend budget.

## Week 4 — reporting and trace viewer (11–15 hours)

Implemented reporting: complete held-out export, raw counts/percentages, task consistency, fault assignment versus exposure, durations including failures, regression counts, known API fees, and incomplete usage. The [read-only local API and Next.js viewer](VIEWER.md) are now implemented and verified against all 216 saved outcomes. Production build and mobile/desktop browser checks passed; all 116 tests pass.

The viewer displays issues, visible model status, tool calls, injection events, patches, verification, and resource usage. It supports missing local artifacts without losing published outcomes, verifies local result hashes, and has no editing or rerun routes. The optional next milestone is a separate disposable patch-review checkout, keeping original study workspaces and outcomes immutable.

Report raw counts and percentages, per-task consistency, fault assignment versus triggering, median/range durations including failures, regression rate, budget exhaustion, and cost per verified success (null when none succeed). Keep scripted runs out of research tables. Any interval must resample tasks rather than runs. Publish reproduction commands, frozen manifest, limitations, raw results, and a short negative-result-friendly narrative.
