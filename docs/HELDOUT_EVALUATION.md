# Frozen held-out evaluation

## Results

All **216/216 scheduled slots** finished with durable results. There were no interruptions, replacement attempts, exclusions, infrastructure-invalid outcomes, or exhausted budgets. **111/216 (51.4%)** repairs passed independent defect and regression checks. Of 168 independently graded submissions, 57 failed the defect check and none failed the regression check. The remaining 48 attempts stopped as agent errors before submission. No unsuccessful attempt was rerun away.

| Architecture | All verified | Clean verified | Assigned-fault verified | Faults triggered | Independently graded | Agent errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed | 63/72 (87.5%) | 33/36 | 30/36 | 36/36 | 72 | 0 |
| Single | 12/72 (16.7%) | 6/36 | 6/36 | 6/36 | 24 | 48 |
| Team | 36/72 (50.0%) | 18/36 | 18/36 | 21/36 | 72 | 0 |

The fixed workflow had the most verified completions in this specific frozen study. This is not evidence that it generally outperforms other architectures. Shared resource ceilings do not make the workflows equivalent: fixed uses predetermined context acquisition and two model stages, team uses four model stages, and single controls its own loop and submission. The model, task design, completion contract, and stop rules all influence these outcomes.

### Per-task consistency

Each cell contains **clean verified out of three, then assigned-fault verified out of three**. Every cell happened to be 0/3 or 3/3; these repetitions do not provide independent evidence from different tasks. Task definitions are listed in [the held-out design](HELDOUT_DESIGN.md).

| Task | Assigned fault | Fixed (clean, fault) | Single (clean, fault) | Team (clean, fault) |
| --- | --- | --- | --- | --- |
| heldout-01 | timeout | 3/3, 3/3 | 3/3, 3/3 | 3/3, 3/3 |
| heldout-02 | timeout | 3/3, 3/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-03 | malformed | 3/3, 0/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-04 | timeout | 3/3, 3/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-05 | malformed | 3/3, 3/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-06 | malformed | 3/3, 3/3 | 0/3, 0/3 | 3/3, 3/3 |
| heldout-07 | timeout | 3/3, 3/3 | 3/3, 3/3 | 3/3, 3/3 |
| heldout-08 | timeout | 3/3, 3/3 | 0/3, 0/3 | 3/3, 3/3 |
| heldout-09 | malformed | 3/3, 3/3 | 0/3, 0/3 | 3/3, 3/3 |
| heldout-10 | timeout | 3/3, 3/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-11 | malformed | 0/3, 0/3 | 0/3, 0/3 | 0/3, 0/3 |
| heldout-12 | malformed | 3/3, 3/3 | 0/3, 0/3 | 3/3, 3/3 |

All architectures failed every explicitly empty-key case. The fixed workflow also failed all three faulted default-page-size cases after passing all three clean cases. These are retained negative outcomes, not grounds to change the frozen rules or claim an improved score on a retuned rerun. Future tuning must use separate development cases and a new evaluation design.

### Fault assignment and triggering

Of **108 assigned faults**, **63 triggered**: 42 timeouts and 21 malformed log responses. Each architecture had 18 timeout and 18 malformed assignments. Actual exposure was:

| Architecture | Timeouts triggered | Malformed logs triggered |
| --- | ---: | ---: |
| Fixed | 18/18 | 18/18 |
| Single | 6/18 | 0/18 |
| Team | 18/18 | 3/18 |

No single-agent malformed assignment reached the log fault. Its identical clean and fault success totals therefore do not establish log-fault recovery. Team also had limited malformed exposure. Fixed had 18/18 verified timeout assignments and 12/18 verified malformed assignments. Access to a valid tool response does not by itself establish correct repair, and triggered-only results must not replace the assigned-run denominator.

### Failures, duration, and usage

All **48 agent errors** occurred in single-agent runs: 30 stopped after requesting the same unchanged content three times, 12 stopped after two consecutive empty turns without submission, and six hit the local token-repetition guard. The latter retain their usage reservations and use the frozen failure classification described in [the prior diagnosis](REPETITION_DIAGNOSIS.md); that classification does not prove that model-server behavior is irrelevant. There were no other error statuses. Zero regression failures among 168 graded submissions means zero failures detected by this small regression suite, not broad preservation of all API behavior.

| Architecture | Median seconds, all outcomes | Range, seconds | Median seconds, successes | Reported tokens | Model requests | Incomplete usage |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Fixed | 8.47 | 5.11–18.03 | 8.51 | 184,659 | 144 | 0/72 |
| Single | 6.62 | 3.44–17.03 | 15.12 | 289,742 | 268 | 6/72 |
| Team | 13.76 | 10.06–51.61 | 15.02 | 315,475 | 288 | 0/72 |

Single's shorter all-outcome median includes many early failures; it is not a time-to-success advantage. Across the study, the all-outcome median was 11.00 seconds, with a 3.44–51.61 second range. All durations include grading when a submission was graded.

There were **700 generation requests** and **789,876 reported tokens**. Six single-agent attempts on heldout-09 have incomplete usage, with **8,646 uncertain reserved tokens** retained separately. Reported totals are a lower bound; reserved tokens are allowances, not measured additional consumption. The complete-usage cost-per-success field is null for single and overall rather than imputing missing usage. API fees are zero under local inference; hardware and electricity are unmeasured.

The [complete result export](studies/heldout-v1-results.json) includes all 216 trial records, the frozen manifest, per-condition aggregates, task consistency, and artifact hashes. Its manifest SHA-256 matches the published zero-attempt preparation. All **109 automated tests passed**, including Docker integration and nine new read-only report checks. The frozen runtime source was not changed during evaluation or reporting.

## Scope and frozen configuration

This study evaluates the twelve mechanically validated held-out defects, using three architectures, three repetitions, and two conditions per task: **216 scheduled slots**. Every task has a clean condition and one assigned fault. Six tasks receive a timeout before a public test executes; six receive one malformed log envelope. Each of the four task categories contains both fault types. Architecture order is seeded within task/repetition/condition blocks; conditions remain clean-first. Task authoring and reference validation were completed before any held-out model generation.

The runtime is frozen at source commit `9130c42be4ed6458c04affa8393004c411c74fe2`, with `completion-v5`, `bounded-actions-v4/fixed-context-v1/logs-v2`, `visible-history-v1`, and `qwen-tokenizer-v1`. The later preparation documentation commit changed no runtime source. All architectures share limits of 20 tool calls, 600 seconds, 24,000 tokens, and $0.25 API fees per attempt. Local Qwen2.5-Coder 7B uses temperature 0, seed 20261030, context 8192, and at most 1024 output tokens per request. Exact model, template, tokenizer, Docker image, and installed environment fingerprints appear in the frozen manifest and [preparation evidence](studies/heldout-v1-preparation.json).

No prompt, task, model, budget, or architecture changes are permitted from inspected held-out outcomes. Development pilots remain separate and are not pooled into these counts. The reporting program lives outside the frozen runtime in `analysis/heldout_report.py`; it reads the ledger and artifacts without changing them. Its descriptive metrics follow the existing study plan.

## Accounting and verification

The append-only ledger records an execution start before work and retains terminal outcomes, including candidate errors, exhausted budgets, infrastructure-invalid results, and interruptions. Resume starts only unstarted slots. Saved final results can be reconciled after interruption without generating another attempt. There are no automatic retries, replacement attempts, or exclusions. Independent defect and regression checks determine verified completion, rather than submission status or public tests alone.

The exporter requires every scheduled slot to have an execution start and a terminal event. It checks the frozen design digest, manifest binding, slot identities, start configuration digests, result paths and SHA-256 hashes, and agreement between completion flags and independent checks. Interrupted slots remain in the denominator with incomplete usage. Raw visible traces, exact local model requests, patches, manifests, results, and the SQLite ledger remain local under `runs/heldout-v1/`.

## Interpretation limits

These defects belong to one small issue-tracker application, share code with development tasks, and are author-written mutations. New contract cases do not establish generalization to independent applications or real production defects. Repetitions share tasks and seeds and must not be treated as independent task samples. Temperature zero does not guarantee identical local generations. Raw counts and per-task consistency are descriptive; no statistical significance or general architecture ranking is claimed.

Fault assignment is the primary grouping. Whether a fault actually triggers depends on an architecture's tool choices. Triggered-only outcomes are selected observations, not a randomized comparison. The fixed workflow deterministically reads logs and retries one eligible decoding failure; this changes context acquisition and model-stage allocation together and is not a retry-only ablation.

Saved durations include independent grading and failures. The injected timeout returns immediately before test execution rather than simulating network delay. Differences in elapsed time may reflect skipped public test work. This is a sequential run on the user's workstation; reporting preparation and brief status reads occurred concurrently, so timing is operational evidence rather than an isolated hardware benchmark.

API fees for local inference are zero. Hardware and electricity are not measured. Missing usage and uncertain token reservations must remain explicit rather than being treated as free or complete usage.

## Reproduce and export

From the matching frozen runtime and installed environment, see [study preparation and resume](STUDY_RUNNER.md). Running again in the existing study directory does not replace failed attempts. A fresh study requires a new preparation directory and must be reported as a separate replication, without tuning from these held-out outcomes.

After all scheduled slots have terminal records:

```powershell
.\.venv\Scripts\python analysis/heldout_report.py runs/heldout-v1 --output docs/studies/heldout-v1-results.json
```

The exporter refuses an incomplete study or an existing output file. Preserve prior exports and all unsuccessful attempts.
