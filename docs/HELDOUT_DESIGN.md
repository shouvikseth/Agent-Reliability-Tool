# Held-out task design and mechanical validation

The development configuration is selected from the completed development pilots. The new held-out catalog is authored separately in `lab/heldout.py`, outside the development `TASKS` list and live pilot CLI. No held-out model generation has been performed. The catalog is a set of additional defects in the same small application, not a new domain or an independent sample of real software projects.

## New contract cases

| ID | Category | Defect being checked |
| --- | --- | --- |
| heldout-01 | Pagination | Reversed ID ordering |
| heldout-02 | Pagination | Returning more rows than the requested limit |
| heldout-03 | Pagination | Incorrect default page size |
| heldout-04 | Validation | Accepting negative offsets |
| heldout-05 | Validation | Accepting a limit above 100 |
| heldout-06 | Validation | Failing to trim nonblank titles in responses and storage |
| heldout-07 | Transitions | Reporting closure without persisting it |
| heldout-08 | Transitions | Closing additional issues |
| heldout-09 | Transitions | Returning an incorrect state after closure |
| heldout-10 | Duplicates | Conflating differently cased request keys |
| heldout-11 | Duplicates | Failing to retain an explicitly empty key |
| heldout-12 | Duplicates | Looking up another key's record |

These have distinct seeded source hashes from every development task. Some edits touch the same functions or anchors as development mutations; they test new contracts or boundaries, not domain generalization. Each issue description and synthetic log states the public contract without providing a reference patch. Reference source and defect checks remain author-only and must never be mounted into candidate containers.

## Selected configuration

Keep `completion-v5`, `bounded-actions-v4/fixed-context-v1/logs-v2`, `visible-history-v1`, and `qwen-tokenizer-v1`. Use the pinned Qwen2.5-Coder 7B model and template, temperature 0, seed 20261030, context 8192, and output limit 1024 per request. All three architectures share limits of 20 tool calls, 600 seconds, 24,000 tokens, and $0.25 API fees per attempt. Local inference has zero API fees; hardware and electricity remain unmeasured. The validation artifact records expected provider fingerprints and stage prompt hashes; it does not assert that the installed provider has passed live preflight.

The design contains **216 slots**: 12 tasks × 3 repetitions × 2 conditions × 3 architectures. Every task has clean and one assigned fault condition. Six tasks receive timeouts and six receive malformed logs. Each category contains both fault types, with alternating 2:1 and 1:2 allocations across its three tasks. Architecture order is seeded within each task/repetition/condition block. Conditions remain clean-first within each block, so ordering is not fully randomized.

Slot IDs are deterministic UUIDs derived from design version, seed, task definition hash, repetition, condition, and architecture. They identify scheduled slots, not executions. The future attempt ledger must attach separate execution IDs, configuration fingerprints, and any authorized replacement relationships; reusing a slot ID must not overwrite an attempt.

## Validation and provenance

All twelve cases passed mechanical Docker validation at source commit `34a026f5864025482dffdaa62ed4731b13206a4b`. The [validation artifact](studies/heldout-v1-validation.json) preserves all 48 individual check results and 216 design slots. All **85 automated tests passed**, including Docker integration. The artifact explicitly records `execution_ready: false` and zero held-out model runs.

The author-only command uses Docker for both seeded and reference checks and never sends a model generation request:

```powershell
.\.venv\Scripts\python -u -m lab.heldout --output runs/heldout-validation-local.json
```

It requires a committed, clean source tree, refuses an existing output path, and records every validation outcome. Every valid task must fail the seeded defect check with exit code 1, pass its seeded regression check, and pass both checks after the reference edit. The evidence includes source commit, immutable Docker image ID, task definitions and normalized source/test hashes, expected configuration, and all 216 design rows. Failed validation produces a nonzero exit and is retained. Mechanical authoring corrections, if needed, precede model evaluation and must receive a new evidence artifact rather than replacing old records.

The existing `lab.cli schedule` is retained as the historical placeholder design. The validated design lives in the new artifact, and the development pilot remains restricted to development tasks.

## Remaining gate before model evaluation

The validation artifact alone does not enable execution of the 216 slots. The subsequent [study runner](STUDY_RUNNER.md) adds an append-only attempt ledger, durable starts/outcomes, interruption reconciliation, pending-only resume, and live preflight. Prepare a separate runnable manifest from a clean committed checkout after those controls pass their tests. The original validation artifact retains its historical `execution_ready: false` value. No model requests are needed for preparation.

Once held-out generations start, do not change prompts, architecture rules, model, budgets, or tasks based on their outcomes. Report every scheduled slot, fault assignment and actual triggering separately, regressions, incomplete usage, and infrastructure exclusions. Keep development evidence separate. Repetitions share tasks and seeds; avoid treating 216 runs as independent task samples.
