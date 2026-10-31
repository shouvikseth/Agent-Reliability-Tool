# Fixed workflow: 60 development consistency trials

## Frozen scope

Source commit `23f9bef75567724d4041007f4cf27fdce83ae5f8` adds an architecture selector to the development pilot without changing the default three-architecture schedule. This batch selects only `fixed`: ten development tasks, three repetitions each, run clean and then under the canonical task-level fault assignment. All 60 outcomes belong to this revision; earlier pilots remain separate.

The frozen settings are `completion-v5`, `bounded-actions-v4/fixed-context-v1/logs-v2`, `visible-history-v1`, and `qwen-tokenizer-v1`. Each run has 20 tool calls, 600 seconds, 24,000 tokens, and a $0.25 API budget; local inference has no API fee. Qwen2.5-Coder 7B uses temperature 0, seed 20261030, an 8,192-token context, and at most 1,024 output tokens per request. The pinned model digest, Docker image, and per-run settings are included in the result exports.

The first four canonical tasks receive one timeout before a public test executes (12 assignments). The remaining six receive one malformed log envelope (18 assignments). Fixed acquisition reads source and logs before patching, and retries an eligible malformed log response once. A retry regaining valid context is a tool recovery outcome; successful defect repair still requires both independent defect and regression checks.

## Results

Every scheduled run submitted and received independent defect and regression checks. No trial was excluded, replaced, or classified as an infrastructure failure. All runs used two model requests and had complete usage records, with no uncertain token reservations or exhausted budgets.

| Measure | Clean | Assigned faults |
| --- | ---: | ---: |
| Verified repairs | 23/30 (76.7%) | 23/30 (76.7%) |
| Regression failures | 0/30 | 1/30 (3.3%) |
| Assigned / triggered faults | 0 / 0 | 30 / 30 |
| Median duration, all outcomes | 10.09 s | 8.93 s |
| Duration range | 7.36–34.09 s | 4.97–15.30 s |
| Reported input + output tokens | 76,535 | 78,753 |
| Model requests | 60 | 60 |
| Cached public test calls | 3 | 0 |
| API fees | $0 | $0 |

The saved duration includes independent grading. The injected timeout returns immediately before executing a public test, rather than waiting for a real network timeout; some runs therefore skip test execution. These timings do not establish a fault-related speed improvement.

| Development task | Clean verified | Fault verified | Assigned fault |
| --- | ---: | ---: | --- |
| pagination-final | 3/3 | 3/3 | Timeout |
| pagination-offset | 3/3 | 3/3 | Timeout |
| blank-title | 2/3 | 3/3 | Timeout |
| missing-issue | 3/3 | 3/3 | Timeout |
| repeat-close | 0/3 | 0/3 | Malformed logs |
| request-replay | 3/3 | 3/3 | Malformed logs |
| request-conflict | 3/3 | 3/3 | Malformed logs |
| filter-state | 3/3 | 2/3 | Malformed logs |
| log-limit-zero | 0/3 | 0/3 | Malformed logs |
| log-title-length | 3/3 | 3/3 | Malformed logs |

Seven tasks passed all three repetitions in each condition. Pairing by task/repetition yields 22 passes in both conditions, six failures in both, one clean-only pass, and one fault-only pass. Equal aggregate rates do not imply identical behavior or fault immunity.

All **18/18 malformed-log assignments** produced a failed decode followed by exactly one successful acquisition retry. All 60 runs had valid context before patching. Nevertheless, only **11/18 malformed-log runs** repaired the defect: recovery of tool access is distinct from repair correctness. All **12/12 timeout assignments** triggered and verified, but none made another public test call after the injected failure. Independent grading still ran fresh for every submission.

The recurring zero-limit failures left the candidate unchanged. Repeated-close failures edited request-key handling instead of repairing repeated closure. The single failed clean blank-title patch added a field option while leaving the broken blank-title guard unchanged. The failed faulted state-filter patch introduced incorrect SQL bindings and failed both independent checks; it remains counted as a regression and a failed repair. These observations identify development weaknesses, not reasons to remove outcomes or change the frozen rules during this batch.

Validated exports: [clean outcomes](pilots/fixed-consistency-clean-30.json), [fault outcomes](pilots/fixed-consistency-fault-30.json), and [per-run acquisition evidence and matched outcomes](pilots/fixed-consistency-acquisition.json). Acquisition evidence includes trace hashes, log attempts, public test-call counts, and run IDs. Local raw pilots are `runs/pilot-fa96fc54977349d7ab805a3d94d7272e` (clean) and `runs/pilot-6bb354c4f43041e19d675eda360c98e4` (faulted).

All **83 automated tests passed** in the final full-suite check with `LAB_DOCKER_TESTS=1`, including Docker integration and the new fixed-only schedule coverage.

## Reproduce

With the Docker image and pinned local tokenizer already installed:

```powershell
foreach ($condition in @('clean', 'injected')) {
    .\.venv\Scripts\python -u -m lab.pilot --tasks pagination-final pagination-offset blank-title missing-issue repeat-close request-replay request-conflict filter-state log-limit-zero log-title-length --architectures fixed --repetitions 3 --tokenizer-file diagnostics/qwen-tokenizer.json --condition $condition
}
```

Export each printed pilot directory independently with `python -m lab.report <pilot-directory> --output <new-json-file>`. The exporter rejects incomplete schedules and existing output paths. Raw traces, exact local model requests, patches, grading results, and manifests remain under the corresponding local `runs/pilot-*` directories.

## Interpretation limits

These are small, previously inspected development tasks. Repetitions use the same model seed and are not independent task samples; temperature zero does not guarantee identical generations. The batch does not estimate held-out performance or compare architectures. It also does not isolate a causal retry effect: deterministic context acquisition and model-stage allocation changed together in the preceding revision. No failed trial is replaced by a successful rerun.

The next study gate is to freeze the chosen development configuration and author and mechanically validate held-out defects before running the planned evaluation. The 216-assignment held-out design is still a placeholder, and the trace viewer remains unimplemented. External API fees exclude hardware and electricity.
