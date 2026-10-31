# Stage-specific completion pilot

## Change

`completion-v3` routes completion guidance by the current stage. Only the single agent sees an explicit submit example; only the final revision sees the empty-action completion example. Other stages describe their next handoff. No empty action list is silently treated as submission. Shared prompts still discourage repeating passed tests without new edits/evidence. Both providers record stage instruction hashes and the rule version.

The implementation and tests were frozen at commit `22eb395`. All 42 unit/provider/Docker tests passed before the pilot. This includes actual provider request routing, explicit no-change revision behavior, and deterministic pilot scheduling. No code or prompt changes were made during the pilot.

## Design

Four development tasks cover pagination (`pagination-offset`), validation (`blank-title`), state transitions (`repeat-close`), and duplicates (`request-conflict`). Every task ran once under each architecture with clean tools, for 12 scheduled trials. Architecture order was shuffled within task/repetition blocks with seed 20261030. Full schedule, manifests, outcomes, budgets, model/image identifiers, and usage are exported in [completion-v3.json](pilots/completion-v3.json).

All trials used the same local Qwen2.5 Coder 7B digest, 8192 context, 1024 maximum output tokens, 24,000 aggregate token budget, 20 tool calls, 600-second deadline, Docker image, and seed. All model API fees were zero; electricity/hardware costs were not measured. Inference ran sequentially on the local GPU. Model seed and temperature zero do not guarantee determinism.

## Results

| Development task | Fixed | Single | Team |
| --- | --- | --- | --- |
| Pagination offset | Verified | Context allowance exhausted | Submitted no patch; defect check failed |
| Blank title | Verified | Submitted no patch; defect check failed | Tool budget exhausted |
| Repeated closure | Verified | Context allowance exhausted | Tool budget exhausted |
| Request-key conflict | Verified | Verified | Verified |
| Verified / scheduled | 4/4 (100%) | 1/4 (25%) | 1/4 (25%) |

Six trials reached verified completion. Two submitted candidates failed the defect check while passing regression. Four trials exhausted a resource allowance before submission and received no independent grade; their existing workspace changes are not counted as successes. There were no infrastructure-invalid outcomes in this pilot. All scheduled outcomes were retained.

## Interpretation and next work

Stage-specific guidance removed the broad empty-revision example from single-agent requests, but did not eliminate context exhaustion, redundant tool use, or no-patch submissions. The fixed workflow completed all four selected tasks in this pilot. One repetition on four self-authored development tasks is insufficient for an architecture ranking or consistency claim. Earlier versions were tuned on development feedback and must not be pooled into a frozen comparison.

Next, inspect the failed traces and choose a documented policy for bounded stage actions and context admission. Apply any policy consistently, version it, and pilot on all eight development tasks with repetitions before freezing. A tokenizer-exact local admission mechanism or a less conservative measured policy would improve interpretability: current UTF-8-byte estimates can stop runs despite reported prompt token counts fitting the model context. Preserve the existing failures; do not raise limits selectively or convert unsubmitted patches into successes. Held-out authoring and evaluation remain future work.

Full traces, patches, and per-run files remain local under `runs/pilot-db7820aa948048488e2d41d91669392f/`. The public JSON export contains outcomes and reproducibility metadata, not credentials or machine paths.
