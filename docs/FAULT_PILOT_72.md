# Matched development fault pilot: 72 additional trials

Completed all 72 assigned-fault trials and matched them to the 72 clean trials: eight development tasks × three architectures × three repetitions in each condition. No outcome was excluded, replaced, or automatically rerun. All 144 records remain available. This is development evidence, not a held-out experiment.

## Frozen configuration

The fault schedule was frozen at commit `6d9a37e`; the clean schedule used `5cf1cd1`. The intervening executable changes add condition scheduling and reporting only. Pairwise checks verified identical model digest, base/stage prompt hashes, admission/context policies, execution policy, budgets, and Docker image for all 72 matched pairs. The seeded architecture order inside task/repetition blocks is identical. Local GPU inference ran sequentially without concurrent diagnostic inference, and no paid provider was used.

The first four canonical development tasks (final-record pagination, offset pagination, blank title, missing issue) were assigned one first-test-call timeout each. The last four (repeated closure, request replay, request-key conflict, filtering) were assigned one first-log-read corruption each. Task assignment is stable across architectures and repetitions. No agent was forced to invoke a tool to obtain exposure.

The timeout is injected before command execution, without a real waiting interval. Its semantics represent a missing test response, not the latency of a production timeout. The log fault returns `{malformed-response` as log text. Since normal log results are also strings, this is **log-content corruption**, not an invalid typed response envelope or malformed transport JSON. These distinctions must remain explicit in any later study.

## Primary assigned-condition results

| Architecture | Clean verified | Assigned-fault verified | Fault actually triggered |
| --- | --- | --- | --- |
| Fixed workflow | 18/24 (75.0%) | 18/24 (75.0%) | 12/24 |
| Single agent | 8/24 (33.3%) | 8/24 (33.3%) | 4/24 |
| Planner/writer/reviewer | 17/24 (70.8%) | 15/24 (62.5%) | 14/24 |

Forty-one of 72 assigned-condition runs verified, compared with 43 of 72 clean runs. Thirty assigned faults triggered and 42 did not. Untriggered assignments remain in the primary denominators. Triggered-only rates select architectures/tasks that reached the affected tool and cannot be interpreted as a fair causal architecture comparison.

## Fault-specific results

Each row covers four tasks × three repetitions for that architecture, with the clean comparison restricted to those same tasks.

| Fault assignment | Architecture | Clean verified | Assigned verified | Triggered | Verified among triggered |
| --- | --- | --- | --- | --- | --- |
| Pre-test timeout | Fixed | 9/12 | 9/12 | 12/12 | 9/12 |
| Pre-test timeout | Single | 4/12 | 4/12 | 4/12 | 4/4 |
| Pre-test timeout | Team | 9/12 | 7/12 | 12/12 | 7/12 |
| Log-content corruption | Fixed | 9/12 | 9/12 | 0/12 | Undefined |
| Log-content corruption | Single | 4/12 | 4/12 | 0/12 | Undefined |
| Log-content corruption | Team | 8/12 | 8/12 | 2/12 | 2/2 |

Only two of 36 log assignments were exposed, both team request-replay runs that verified. This provides very little evidence about corrupted-log handling and none about malformed transport recovery. Zero exposure for fixed/single must not be presented as successful recovery.

The two team timeout losses were pagination-offset repetitions 2 and 3: their clean counterparts verified, while assigned runs produced incomplete model responses. No other timeout pair changed its binary outcome. In the log-assigned block, two team filtering pairs swapped outcomes (one gained and one lost), although neither actually read logs. Thus differences between untriggered runs are not evidence of fault causation, even with the same seed and settings.

## What verified completion means here

The grader independently checks submitted patches regardless of whether public tests ran. A verified patch after a fault does not prove the agent retried or understood the tool failure. In the timeout block, trace inspection found no later public test calls after the injected error for fixed/team. The single-agent block had two later test requests across its four exposed runs. These are behavioral observations, not an additional grading criterion. Hidden checks remained external to candidate containers.

The assigned batch had 54 graded submissions: 41 passed both checks and 13 failed at least one. Six submitted patches failed regression (three fixed and three team). Eighteen runs did not submit: 16 single-agent trials and two team incomplete-response failures. One local repetition abort retained an uncertain token allowance rather than inventing usage. No infrastructure-invalid outcome occurred. All model failures and budget stops are retained.

## Data and verification

- [Assigned-trial outcomes and resource metrics](pilots/development-fault-72.json)
- [Validated matched-pair and exposure counts](pilots/development-matched-144.json)
- [Clean baseline report](DEVELOPMENT_PILOT_72.md) and [clean outcomes](pilots/development-clean-72.json)

Raw assigned traces, request artifacts, patches, manifests, and SQLite results remain local under `runs/pilot-6710088711094b76aedec3f51b144955/`. Public exports contain outcomes and configuration metadata, not credentials or raw requests. The report generator refuses incomplete, duplicated, unexpected, or mismatched-condition records. All 68 automated tests passed, including schedule balance, unchanged architecture order, canonical task-level assignment, Docker isolation, and report accounting.

The assigned pilot can be reproduced with:

```powershell
.\.venv\Scripts\python -u -m lab.pilot --tasks pagination-final pagination-offset blank-title missing-issue repeat-close request-replay request-conflict filter-state --repetitions 3 --tokenizer-file diagnostics/qwen-tokenizer.json --condition injected
```

External API fees were zero; hardware/electricity costs were not measured. Timings are descriptive: clean trials preceded assigned trials rather than counterbalancing condition order, machine power/thermal state was uncontrolled, and injected timeouts omit a real waiting interval. Fault types are assigned to different task subsets, so their rates should not be directly ranked. Repetitions are related observations on eight self-authored, previously tuned development tasks; no confidence intervals, broad architecture ranking, or isolated reviewer benefit is claimed.

## Next development gate

Before a held-out freeze, define a typed log-tool response contract and distinguish content corruption from response-envelope corruption. Add development tasks with useful, behaviorally relevant logs; do not force log calls merely to increase exposure or revise these outcomes after the fact. Revalidate the revised contract and injection mechanisms on development tasks. Held-out task authoring, experiment freeze, the planned 216 held-out trials, and viewer work remain future stages. Preserve the present 144-run dataset as the current baseline.
