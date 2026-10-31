# Bounded fixed-workflow context acquisition

Implemented and froze `fixed-context-v1` at source commit `e925e04`. The execution policy is now `bounded-actions-v4/fixed-context-v1/logs-v2`. Earlier pilots remain unchanged and are not pooled with this revision.

## Predetermined control flow

The fixed workflow performs one `read app.py`, then one `logs` request. It retries logs at most once, and only when the typed error is `invalid_log_response` with `retryable: true`. A second invalid result, a nonretryable error, or a resource limit stops acquisition before any model patch request. Every call consumes the existing tool/time budget and is recorded in history and trace events.

Once source and valid logs are available, the model proposes a patch, the orchestrator runs public tests, and one model revision stage follows before explicit orchestrator submission. The former model-selected inspection response has been replaced by deterministic acquisition: there are now **two model stages**, patch and revision, rather than three. There is no automatic patch retry, implicit success, unlimited tool retry, or additional budget. Single-agent and team control flow remain unchanged.

This is a workflow revision affecting both context completeness and call allocation, not an isolated retry ablation. It forces the fixed workflow to read supplied logs even on tasks where they may be unnecessary. That overhead and difference from agent-selected tool use must be included in future comparisons.

All **82 tests passed**, including Docker integration, clean acquisition, a single eligible retry, permanent failure after two attempts, no model request after inspection budget exhaustion, shared usage, and exact model-stage counts.

## Four local smoke trials

Ran two log-informed development tasks, one repetition each, clean and malformed-log conditions. Source, prompts, model digest, seed, container, and budgets were held constant. All runs used two model requests and had complete usage records. External API fees were zero; hardware/electricity costs were not measured.

| Task | Condition | Log calls | Valid log responses | Independent verification |
| --- | --- | --- | --- | --- |
| Zero limit | Clean | 1 | 1 | Failed defect check; regression passed |
| Title length | Clean | 1 | 1 | Passed both |
| Zero limit | Malformed | 2 | 1 | Failed defect check; regression passed |
| Title length | Malformed | 2 | 1 | Passed both |

Both malformed faults triggered and were retried once during acquisition. Both runs therefore had valid logs before the patch stage. Repair completion was **1/2 clean and 1/2 faulted**, not 100%. Deterministic tool recovery does not imply a correct patch. Neither failed workspace was salvaged into a success or rerun away.

The previous fixed-workflow log pilot had 1/2 clean and 0/2 faulted successes, but one repetition and a changed inspection procedure do not establish a causal improvement. No new results for the other architectures are claimed.

Complete results and acquisition counts: [fixed-context-v1.json](pilots/fixed-context-v1.json). Raw traces, request captures, patches, and manifests remain local under `runs/fixed-context-v1/`.

## Reproduce

```powershell
.\.venv\Scripts\python -m lab.cli run --provider ollama --backend docker --architecture fixed --task log-title-length --fault malformed --max-seconds 600 --tokenizer-file diagnostics/qwen-tokenizer.json
```

Next: run development consistency checks under this revised contract before a final freeze. Preserve the earlier 144-run baseline and typed-log pilot separately. Held-out task authoring and the planned 216-trial evaluation remain future work; do not tune the architecture against held-out outcomes.
