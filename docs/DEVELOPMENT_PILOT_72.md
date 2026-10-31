# Frozen clean-tools development pilot: 72 trials

All 72 scheduled outcomes are recorded: eight development tasks × three architectures × three repetitions. Forty-three submitted patches passed both independent defect and regression checks. No trial was excluded, replaced, or silently rerun. No infrastructure-invalid outcome occurred; a known token-repetition abort counted as a generation failure with uncertain usage retained.

## Configuration and provenance

The executable configuration was frozen at commit `5cf1cd112279bb4c157f49c0ea15fd3828cf0776`. No prompts, model settings, budgets, task definitions, tools, or graders changed during execution. Analysis/report code was authored separately and does not alter runner behavior.

Every trial used Qwen2.5 Coder 7B digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, `completion-v4`, `bounded-actions-v2`, `visible-history-v1`, fingerprinted `qwen-tokenizer-v1`, temperature zero, and seed 20261030. Budgets were 24,000 aggregate tokens, 20 tool calls, 600 seconds, 8192 context, and 1024 maximum output tokens per request. The Docker image identifier was identical across runs. Architecture order was shuffled within task/repetition blocks using the recorded seed.

Model inference ran sequentially on the local RTX 4070 Laptop GPU. No diagnostic inference ran concurrently. The same seed does not guarantee deterministic output. GPU power/thermal state and host activity were not experimentally controlled, so latency is descriptive. The held-out task set was not used or created by this experiment.

Full schedule, per-trial results, provider fingerprints, aggregate counts, resource usage, and consistency are in [development-clean-72.json](pilots/development-clean-72.json). Raw traces, exact request payloads, patches, and manifests remain locally under `runs/pilot-eb763b598d874cbdbd1194c4613d449a/`. Raw requests and credentials are not part of the public report.

## Verified completion

| Architecture | Verified / scheduled | Completion | Submitted and graded | Failed regression / graded |
| --- | --- | --- | --- | --- |
| Fixed workflow | 18/24 | 75.0% | 24 | 3/24 |
| Single agent | 8/24 | 33.3% | 8 | 0/8 |
| Planner/writer/reviewer | 17/24 | 70.8% | 24 | 3/24 |

The single agent's zero observed regressions are conditional on its eight submissions; sixteen runs never reached grading. This is not evidence that it is universally safer.

## Per-task consistency

Each cell is verified successes out of three repetitions.

| Development task | Fixed | Single | Team |
| --- | --- | --- | --- |
| Pagination final record | 3/3 | 3/3 | 3/3 |
| Pagination offset | 3/3 | 0/3 | 3/3 |
| Blank title | 0/3 | 0/3 | 3/3 |
| Missing issue | 3/3 | 1/3 | 0/3 |
| Repeated closure | 3/3 | 1/3 | 0/3 |
| Request replay | 3/3 | 0/3 | 3/3 |
| Request-key conflict | 3/3 | 0/3 | 3/3 |
| State filtering | 0/3 | 3/3 | 2/3 |

The aggregate ordering hides complementary behavior. The team handled blank-title validation where the other implementations failed. The single agent consistently handled state filtering, while the fixed workflow failed all three repetitions. The fixed workflow consistently handled missing issues and repeated closure where the team failed. These are observations on this self-authored development set, not general causal claims.

## Failure accounting

All 56 submissions were independently graded:

- 43 passed both defect and regression checks.
- 7 failed the defect check while passing regression.
- 3 passed the defect check but failed regression.
- 3 failed both.

The 16 unsubmitted runs were all single-agent trials:

- 6 stopped after three reads of unchanged content.
- 7 stopped after two empty turns without submission.
- 1 generation aborted at Ollama's token repetition guard.
- 2 exhausted admission capacity within the aggregate token/context budget.

No unsubmitted workspace was salvaged into a success. The generic admission error names token/context allowance; it should not be interpreted as proof that the model's physical context window was full. Both exhausted trials had already consumed more than 21,000 reported aggregate tokens.

## Resources

| Architecture | Model requests | Reported tokens | Median duration, all runs | Median duration, successes | Range, all runs |
| --- | --- | --- | --- | --- | --- |
| Fixed | 72 | 64,777 | 9.99 s | 9.74 s | 8.75–14.59 s |
| Single | 106 | ≥121,966 | 6.55 s | 11.23 s | 1.56–29.19 s |
| Team | 96 | 109,019 | 14.17 s | 13.45 s | 10.34–19.58 s |

The single agent's lower all-run median reflects many early failures, not superior verified throughput. Its reported token total is a lower bound: one generation abort supplied no usage, leaving an unresolved reservation of 1390 tokens. Reservations are allowances, not measured consumption. Nine team test calls reused a passed result for identical source; those calls still consumed tool-call budget, and independent grading always ran fresh.

External model API fees were zero for all trials. Hardware, electricity, and opportunity costs were not measured, so this does not establish zero total cost or a dollar-efficiency ranking. The JSON report conservatively leaves API-cost-per-success null when token usage is incomplete, even though this local backend makes no paid API request.

## Verification and limits

All 67 automated tests passed after execution, including provider/Docker contracts and report checks that reject missing, unexpected, or duplicate outcomes. One result is required for every scheduled task/architecture/repetition combination. All runs used a single model digest, image, and policy version. The report script can reproduce the export:

```powershell
.\.venv\Scripts\python -m lab.report runs/pilot-eb763b598d874cbdbd1194c4613d449a --output diagnostics/recomputed-clean-72.json
```

This is a tuned development study with eight related, small, self-authored defects in one API. Verifier coverage is limited to the included checks; a passing outcome is not proof of universal correctness. Architecture implementations differ in control flow and role prompts, so this is not an isolated reviewer ablation. Repetitions of a task are dependent observations. No confidence intervals or broad statistical ranking are claimed. Earlier pilots used different policies and must not be pooled into this frozen batch.

## Next experiment

Add matched injected-fault trials under this same frozen executable configuration. Record fault assignment and actual triggering separately: log-read faults cannot trigger when no log read occurs. Preserve raw counts and the clean baseline, and retain model failures rather than rerunning them away. Only after development is complete should held-out task authoring, experiment freeze, and the planned 216-trial held-out study proceed. Viewer work remains secondary to auditable CLI evidence.
