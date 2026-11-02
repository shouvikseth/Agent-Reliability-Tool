# Post-study audit of the held-out evaluation

**Date:** November 1, 2026. This audit was run after the study, with its outcomes known. It does not change, replace, or re-score the frozen results. Nothing here was used to tune the runtime, and `lab/` still matches the frozen source fingerprints. Machine-readable evidence is in [the audit export](studies/heldout-v1-audit.json).

## Summary

The bookkeeping holds up and the architecture ordering survived the sensitivity checks. The design is weaker than 216 trials suggests: it is closer to twelve independent cases, it provides little evidence about fault handling, and it does not isolate architecture from workflow differences.

## Confirmed

- Re-exporting from the raw ledger reproduced every published trial and summary exactly.
- `lab/`, `docker/`, `target_app/`, and `pyproject.toml` have not changed since frozen commit `9130c42`. The held-out catalog did not change between validation and that commit, and no earlier saved run used a held-out task.
- All 117 tests pass with Docker enabled, and all ten development tasks validate. A fresh clone installs, builds the viewer, and rebuilds the Docker image from its pins. The rebuilt image has a different ID from the recorded one.
- The OpenAI dependency conflict is real, as the README states.
- A broader regression sweep supports most verified repairs: 108 of 111 behaved the same as the reference across 60 requests, using the same sandbox.

## Findings

### Repetitions are not independent

In 71 of 72 cells, all three repetitions produced an identical patch. Temperature 0 makes generation close to deterministic, so the fixed seed adds little. A seed-only change produced 11, 7, and 2 of 12 clean verified repairs for fixed, team, and single, against 11, 7, and 3 for a same-seed replay.

Per-defect clean results are the more honest reading: fixed solved 11 of 12, team 6, and single 2.

| Comparison | Defects won | Lost | Two-sided sign test |
| --- | ---: | ---: | ---: |
| Fixed vs. team | 5 | 0 | p = 0.0625 |
| Fixed vs. single | 9 | 0 | p = 0.0039 |
| Team vs. single | 4 | 0 | p = 0.125 |

These tests are descriptive and were chosen after the study. Twelve author-written defects in one application remain a narrow sample.

### Public tests never failed

Across the study, all 141 executed public test runs and all 19 cached results passed. The seeded defects pass those tests, and 48 submissions that failed grading had a passing public test. Agents had no failing signal from `test`, so iteration could not be informed by it. This limits what the comparison says about feedback loops, and particularly about the single agent.

### Faults had almost no measurable effect

Injected faults changed the verified result for 1 of 36 task and architecture pairs: fixed on heldout-03, under a malformed log. Timeouts changed none. A timeout removes a test result that carried no signal, so it could not plausibly change a repair. **These results are not evidence of timeout recovery.** They show bounded handling of the fault path, not resilience.

### The comparison is not architecture alone

- After the 72-trial development comparisons, commit `e925e04` gave fixed guaranteed log access. Single and team control flow were not changed. This was permitted development work, but it favored the leading architecture.
- Fixed and team are submitted automatically. Single must submit for itself, so all 48 agent errors were single runs. One single run (heldout-12, clean, repetition 1) reached the exact reference source and was stopped for repeated reads before submitting.
- The two-empty-turns stop applies only to single, even though the shared prompt says actions are optional. Twelve single runs ended this way. Six more single failures came from the local model server's repetition guard before any tool ran.

### One regression went undetected

Three verified fixed runs (heldout-03, clean) accept `GET /issues?limit=0` with status 200. The reference returns 422, and the development task `log-limit-zero` requires it. The regression check is the same four assertions as the public test, so "zero regressions" means zero detected by those assertions. Counted strictly, fixed would have 60 of 72. The frozen score is unchanged.

### Replays are close, not exact

Replaying the original clean configuration matched 34 of 36 task and architecture outcomes. Both differences were heldout-03, for single and team, which passed in the replay. Several other single runs took different paths or stopped differently.

## Sensitivity check

These are 180 separate clean trials on all twelve defects, using the frozen model and limits. Temperature 0.2 is an audit perturbation applied at the request boundary. These trials are not pooled with the study.

| Configuration | Fixed | Team | Single |
| --- | ---: | ---: | ---: |
| Recorded study, clean, per defect | 11/12 | 6/12 | 2/12 |
| Same-seed replay | 11/12 | 7/12 | 3/12 |
| Seed changed, temperature 0 | 11/12 | 7/12 | 2/12 |
| Temperature 0.2, seed 11 | 10/12 | 7/12 | 5/12 |
| Temperature 0.2, seed 12 | 9/12 | 6/12 | 2/12 |
| Temperature 0.2, seed 13 | 9/12 | 6/12 | 2/12 |
| **Temperature 0.2, total** | **28/36 (77.8%)** | **19/36 (52.8%)** | **9/36 (25.0%)** |

Fixed led team, and team led single, in every configuration. Fixed's 87.5% is likely optimistic even for this application and model; these limited runs put clean performance nearer 75–80%. Heldout-11 failed in every temperature 0.2 trial. Two single trials exhausted their context allowance, and three team trials hit the repeated-read stop, so these outcomes are not unique to temperature 0.

## How to cite this work

Supported: in twelve author-written defects in one small application with one local model, fixed solved more clean defects than team, and team more than single, and that order held under replay and small perturbations.

Not supported: a general architecture ranking, fault recovery, timeout resilience, adversarially secure grading, or treating 216 trials as independent.

A stronger replication would use public tests that can fail, faults that remove useful information, several applications, equivalent context and submission rules, and multiple samples per task, with all of this fixed before running.

## Reproduce

From the checkout that holds `runs/heldout-v1`:

```powershell
.\.venv\Scripts\python analysis/post_study_audit.py profile runs/heldout-v1 --output audit.json
.\.venv\Scripts\python analysis/post_study_audit.py differential runs/heldout-v1 --output audit.json
.\.venv\Scripts\python analysis/post_study_audit.py sensitivity runs/audit-sensitivity --output audit.json --tokenizer-file diagnostics/qwen-tokenizer.json
```

Profile needs saved traces, differential needs Docker, and sensitivity needs Docker and the pinned Ollama model. It takes about 30 minutes and generates new model output. Exact replay results may vary.
