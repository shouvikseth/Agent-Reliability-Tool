# Agent Reliability Lab — completion report

**Owner:** Shouvik Seth  
**Report date:** November 1, 2026  
**Handoff:** local research lab, recorded evaluation, and read-only viewer delivered. The free-provider workflow passed a fresh-checkout audit. The optional paid-provider dependency profile has a confirmed unresolved conflict, detailed below.

> This report records the handoff as of its date. Later work added a hosted snapshot and a [post-study audit](POST_STUDY_AUDIT.md) that qualifies its results.

## Delivered scope

- A FastAPI/SQLite issue tracker with ten development defects and twelve separately authored held-out defects across pagination, validation, state transitions, and duplicate-request behavior.
- Fixed, single-agent, and planner/writer/reviewer control flows with shared resource limits, restricted tools, explicit completion, typed log responses, and bounded fault recovery.
- Disposable Docker execution and independent API checks, with provenance, patches, visible traces, usage accounting, and durable results.
- A frozen 216-slot evaluation with append-only attempt records, crash reconciliation, source/model/environment preflight, pending-only resume, and no automatic replacement of failed attempts.
- A local read-only Next.js viewer with task/architecture/condition/outcome filters, grading, visible events, patches, resource usage, incomplete-usage records, manifest inspection, and filtered JSON download.
- Published outcome exports, reproducibility commands, development-pilot history, isolation boundaries, and explicit limitations.

## Evaluation results

The completed study used twelve held-out defects × three architectures × three repetitions × two conditions, for **216 scheduled and completed trials**. Runtime source, model settings, prompts, budgets, and tasks remained frozen. Earlier development studies are preserved separately.

| Architecture | Verified overall | Clean | Assigned faults |
| --- | ---: | ---: | ---: |
| Fixed | 63/72 (87.5%) | 33/36 | 30/36 |
| Single | 12/72 (16.7%) | 6/36 | 6/36 |
| Team | 36/72 (50.0%) | 18/36 | 18/36 |

Overall, **111/216 (51.4%)** repairs passed both independent checks. There were 168 graded submissions, including 57 unsuccessful defect repairs, and 48 agent errors before submission. The small regression suite detected no regressions among graded submissions. No infrastructure-invalid results, exhausted budgets, interruptions, replacement attempts, or exclusions occurred.

Only **63/108 assigned faults triggered**. Six single-agent attempts hit the local token-repetition guard and retain incomplete usage: 8,646 uncertain reserved tokens are separate from 789,876 reported tokens. The study made 700 generation requests. Local API fees were $0; hardware and electricity were not measured. These results describe one small application and dependent repetitions, not a general architecture ranking.

Evidence: [full evaluation report](HELDOUT_EVALUATION.md), [all 216 outcomes](studies/heldout-v1-results.json), and [frozen preparation](studies/heldout-v1-preparation.json).

## Reproducibility checks

Audited a new GitHub clone of `codex/reliability-lab` at source commit `1acf3dfbb58ec7c0ce0d401cdb425c2d42d86d5c`, using a new Python virtual environment and a fresh frontend dependency installation. The final wrap-up changes documentation and a generated-metadata ignore rule; it does not change evaluated runtime code or dependency declarations.

| Check | Result |
| --- | --- |
| Install declared free-provider profile `.[dev,local-tokenizer]` | Passed |
| `pip check` in that environment | No broken requirements |
| Docker-enabled test suite | **115 passed, one skipped, zero failed** |
| Skipped test | Optional installed OpenAI SDK HTTP contract; SDK absent in this free-provider profile |
| All ten development seeds/reference fixes in Docker | All valid |
| `npm ci` from the committed lockfile | Passed; zero vulnerabilities reported at audit time |
| Production viewer build | Passed |
| Viewer without original `runs/` data | HTTP 200; all 216 published outcomes visible; missing traces correctly labeled |
| Original frozen source and result manifest | Still match the recorded fingerprints |
| Model evaluation during this audit | None; the 216-trial study was not rerun |

The original study/viewer environment previously passed all **116 tests**, including the installed-SDK contract. The fresh audit used the existing immutable Docker image; it did not perform a clean image rebuild. This verifies installation and inspection workflows, not an exact replay of model outputs or an independent replication of the study.

Machine-readable evidence: [completion audit](studies/completion-audit-20261101.json).

## Viewer and verification

The local viewer is served by `viewer/server.py` from a built Next.js static export. Its Python server requires only the standard library and binds to loopback. Browser QA verified filters, failed grades, fault events, patches, incomplete usage, empty results, duration sorting, the manifest dialog, a six-record JSON download, and keyboard navigation. Mobile and desktop layouts were checked at 375px and 1440px, without page-wide horizontal overflow. No browser console errors or warnings were observed.

All 216 original local result hashes matched their published records after viewer QA. Missing local files do not erase published outcomes, and mismatched local results are rejected. The viewer exposes no execution or edit controls, does not import candidate source, and does not serve raw model request payloads. [Launch instructions and API](VIEWER.md).

## Limitations and optional follow-up

**Confirmed dependency issue:** the optional `openai` extra cannot currently resolve against the declared base dependencies. The base project requires `anyio==4.9.0`; `openai==3.42.0` requires `anyio>=4.10.0,<5`. A fresh `pip --dry-run` probe failed with this conflict. The README now directs users to the verified free-provider path and identifies the paid-profile limitation. Do not force incompatible dependencies into the free or frozen environment. Resolving the optional profile belongs in a separate source revision with new validation; this report does not claim a working fresh paid-provider install or paid live evaluation.

The historical study host used AnyIO 4.15.1, as recorded in its manifest; the fresh declared free profile installs 4.9.0. Their environments are not interchangeable for strict study resumption. The original metadata is preserved rather than rewritten to conceal that difference.

Other practical limits:

- Results cover synthetic mutations in one application; repetitions share tasks and seeds, and fault exposure depends on tool choices.
- Six token-usage records remain incomplete. No complete token-cost estimate is imputed for them.
- Raw event traces, exact request captures, and candidate workspaces remain local and ignored by Git. A fresh clone includes published outcomes, not the entire local artifact archive.
- Docker/kernel isolation and the candidate response adapter remain trust boundaries. This is not a hardened multi-user execution service.
- The viewer is a loopback-only inspection utility, not an authenticated hosted service. A result hash does not separately authenticate local trace and patch files.

Optional future work includes a corrected paid-provider installation profile, independent replication on new defects/applications, more comprehensive regression coverage, and disposable patch-review workspaces. Such work must preserve the completed study and avoid retuning its reported score from held-out outcomes.

## Handoff

The project is on [GitHub](https://github.com/shouvikseth/Agent-Reliability-Tool/tree/codex/reliability-lab), branch `codex/reliability-lab`. The [README](../README.md) is the current quickstart and result index. No merge or release tag is implied by this handoff.

On the existing workspace, where the viewer has already been built:

```powershell
.\.venv\Scripts\python viewer/server.py
```

Then open [the local viewer](http://127.0.0.1:8765). For a new checkout, use the README's environment-install and frontend-build steps first. The viewer needs no new model generation or API credits.
