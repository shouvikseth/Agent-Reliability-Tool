# Context and bounded-action development pilot

Implemented `completion-v4`, `bounded-actions-v1`, `visible-history-v1`, and Ollama `message-bytes-v2`. See [policy definitions](POLICIES.md). The main changes are message-only admission accounting, deterministic history compaction, six-action batches, cached passing public tests keyed by source, explicit empty-turn feedback, and durable execution evidence before grading. Docker cleanup errors now preserve infrastructure classification and always attempt to reap the local attach process. Local HTTP diagnostics retain status and a fixed category without raw server messages.

## Evidence

The first attempt at source commit `36ab9d6` scheduled 12 trials but stopped during trial 11 when Docker kill timed out in grader cleanup. Ten final results were saved, the eleventh has trace/patch/manifest evidence but no final grade, and the twelfth never started. This attempt is exported separately in [completion-v4-interrupted.json](pilots/completion-v4-interrupted.json). It is not silently discarded or pooled with the fresh batch. No ungraded candidate is counted as a success.

After fixing cleanup propagation and adding durable `execution.json`, a fresh batch was frozen at commit `876e3ed`. All 12 trials finished with result records. [completion-v4.json](pilots/completion-v4.json) contains the schedule, outcomes, model and container identifiers, budgets, hashes, versions, and context-accounting aggregates. Full local traces are under `runs/pilot-f3f2ee2aad254a8db082abea0f75e87d/`.

Every trial used the same local Qwen2.5 Coder 7B digest, seed 20261030, 8192 context, 1024 maximum output tokens, 24,000 aggregate tokens, 20 tool calls, and 600 seconds. Four development tasks each ran once under three architectures with clean tools and seeded architecture ordering. No paid model requests or held-out tasks were used.

| Task | Fixed | Single | Team |
| --- | --- | --- | --- |
| Pagination offset | Verified | Ollama HTTP 500 | Verified |
| Blank title | Defect check failed | Empty-turn stop | Context allowance exhausted |
| Repeated closure | Verified | Context allowance exhausted | Defect check failed |
| Request-key conflict | Verified | Verified | Verified |
| Verified / scheduled | 3/4 | 1/4 | 2/4 |

Six verified successes, two defect-check failures after submission, two context admission stops, one empty-turn stop, and one infrastructure-invalid HTTP failure account for all 12 trials. The HTTP failure remains in the scheduled denominator here, with its classification explicit; there was no automatic rerun substituted for it. Reported model API fees were zero. Hardware/electricity costs were not measured, and the failed HTTP request retained an uncertain token reservation.

Two requested test calls reused a passing result for identical source, avoiding new test-container execution while still counting against the tool budget. Across 48 completed model responses, median admission-bound / reported-input-token ratio was approximately 4.50. Removing the grammar and double escaping makes the calculation better grounded, but it remains far from exact. These diagnostics do not prove improved task completion: total successes matched the prior v3 pilot's six, with a different distribution across architectures.

A separate diagnostic reconstruction of the failed local request returned HTTP 200. It was not substituted for the failed outcome and ran while the fresh batch was active. Consequently these durations are recorded but must not be used as an uncontended speed comparison. The HTTP 500's root cause remains unresolved.

## Validation and next gate

All 51 tests passed, including Docker integration. Automated coverage checks cache invalidation, retry of injected pre-execution faults, non-caching of failures, rejection of oversized batches before any action, immutable context compaction, no implicit submission after empty turns, safe HTTP diagnostics, cleanup timeout propagation/reaping, durable execution/results after grader infrastructure failure, and existing provider/Docker contracts.

Before the planned 72 clean trials across all eight development tasks, resolve recurring local HTTP failures and improve tokenizer/admission validation. Preserve the v3 baseline, both v4 attempts, and the current failed outcomes. Do not selectively raise budgets or retune against held-out results. Fault-condition repetitions, the held-out task set, experiment freeze, full evaluation, and viewer remain outstanding.
