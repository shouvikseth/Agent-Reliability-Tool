# Agent Reliability Lab

A local research lab for comparing a fixed workflow, a single agent, and planner/writer/reviewer orchestration on software repair. The target is a small FastAPI/SQLite issue tracker. Candidate changes execute and are independently checked in restricted Docker containers.

**Completed scope:** ten development defects, twelve separately authored held-out defects, a frozen 216-trial evaluation, complete outcome accounting, and a read-only local trace viewer. See the [completion report](docs/COMPLETION_REPORT.md) for the handoff and fresh-checkout audit.

## Recorded results

| Architecture | Verified repairs | Clean | Assigned faults |
| --- | ---: | ---: | ---: |
| Fixed | 63/72 (87.5%) | 33/36 | 30/36 |
| Single | 12/72 (16.7%) | 6/36 | 6/36 |
| Team | 36/72 (50.0%) | 18/36 | 18/36 |

All 216 slots are accounted for. There were no replacement attempts, exclusions, infrastructure failures, or interruptions. Only **63/108 assigned faults triggered**. Six single-agent records retain incomplete token usage. External API fees were $0; hardware and electricity were not measured.

These are twelve mutations in one small application, with dependent repetitions. The results do not establish a general architecture ranking. Read the [full evaluation and limitations](docs/HELDOUT_EVALUATION.md), [complete result export](docs/studies/heldout-v1-results.json), and [frozen preparation evidence](docs/studies/heldout-v1-preparation.json).

**Read the [post-study audit](docs/POST_STUDY_AUDIT.md) before quoting these rates.** The accounting reproduces exactly, but the design is weaker than the trial count suggests. Repetitions were nearly identical: 71/72 cells produced one patch, so on clean runs the comparison is closer to 11, 6, and 2 of 12 defects for fixed, team, and single. Public tests never failed, injected faults changed one of 36 task outcomes, and development gave fixed its guaranteed log access. In 180 separate clean audit trials the order held (fixed, team, single), though at temperature 0.2 fixed fell to 28/36 and single reached 9/36. The frozen results above are unchanged.

[Explore the hosted study](https://agent-reliability-lab-alpha.vercel.app/), including visible traces and patches for all 216 trials.

## Windows quickstart: view the saved study

Use Python 3.11+ and Node/npm. The verified viewer build used Node 22.20.0. For a new checkout:

```powershell
git clone --branch codex/reliability-lab --single-branch https://github.com/shouvikseth/Agent-Reliability-Tool.git
cd Agent-Reliability-Tool
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev,local-tokenizer]'
npm --prefix viewer ci
npm --prefix viewer run build
.\.venv\Scripts\python viewer/server.py
```

Open [the viewer](http://127.0.0.1:8765). Stop its server with Ctrl+C. Viewing saved outcomes needs no API key, model generation, or running Docker.

The viewer filters all 216 outcomes and shows grades, usage, the frozen manifest, and traces and patches. The hosted snapshot reads them from the committed [evidence export](docs/studies/heldout-v1-evidence.json). This local server reads ignored `runs/` directories instead, so a fresh clone labels them as missing locally. Exact model requests and candidate workspaces are never published. [Viewer guide and API](docs/VIEWER.md).

## Check the implementation

Without Docker integration:

```powershell
.\.venv\Scripts\python -m pytest -q
```

With Docker Desktop's Linux engine running:

```powershell
docker build -f docker/Dockerfile -t agent-reliability-lab:dev .
$env:LAB_DOCKER_TESTS = '1'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m lab.cli validate --backend docker
```

The suite has **117 tests**. The original environment passes all of them with Docker enabled. In a fresh free-provider install, `pip check` passes and tests skip the optional installed-SDK contract, plus seven Docker tests unless `LAB_DOCKER_TESTS` is set. The image also rebuilds from its pins; a rebuilt image has a new ID, so strict study resumption still requires the recorded image. Earlier counts in dated reports describe those moments. [Completion audit](docs/studies/completion-audit-20261101.json) and [post-study audit](docs/POST_STUDY_AUDIT.md).

`validate` checks that every seeded development task fails its defect check, passes regression checks, and passes both after its reference edit. All ten passed in the fresh checkout. `smoke` is a scripted fixture and must not be counted as model evidence. `lab.cli schedule` retains a historical placeholder design; it is not the completed study runner.

## Run a new local development trial

Follow the [Ollama setup guide](docs/OLLAMA.md) for installation, the local Qwen model, and optional pinned tokenizer assets. With the model available and the Docker image built:

```powershell
.\.venv\Scripts\python -m lab.cli run --provider ollama --backend docker --task pagination-final --architecture fixed --max-seconds 600
```

This command uses the default byte-based admission policy. The recorded held-out study used fingerprinted tokenizer admission instead; its exact configuration is in the manifest. Run development experiments separately and label changes. The [study runner guide](docs/STUDY_RUNNER.md) documents preparation, fingerprints, durable starts, interruption reconciliation, and resume behavior. Do not tune on the completed held-out outcomes and reuse them as fresh evidence.

## Optional OpenAI adapter: dependency limitation

The adapter and mocked contracts remain in the source, but the current `openai` extra is not installable together with the declared base dependencies: the project pins `anyio==4.9.0`, while `openai==3.42.0` requires `anyio>=4.10.0,<5`. A fresh resolver check confirmed this conflict. Do not install the paid SDK into the verified free-provider environment or force conflicting dependencies.

Resolving this optional dependency profile requires a separate revision and new validation. Paid live-provider evaluation is outside this handoff; API account access, billing reconciliation, and current pricing would need checking for that work. No paid API requests were made during completion checks. Keep API keys out of chat and command history.

## Execution and accounting boundaries

- Candidate code runs in disposable containers: no network, host mounts, Docker socket, or credentials; non-root UID; read-only root; bounded temporary storage, memory, CPU, processes, and deadlines.
- Independent checks run outside candidate containers against JSON API responses. Candidate source is never imported on the host by Docker grading. Canonical public tests are advisory; defect and regression checks determine completion. Candidates cannot read the checks or change their logic, but they produce the responses being checked, so grading is not tamper-proof against adversarial code.
- Local/host execution is for trusted development fixtures only. Live model runs require Docker. This is a local research isolation layer, not a hardened multi-tenant service; candidates can tamper with their own response stream, and Docker/kernel isolation remains a dependency.
- The frozen study ledger preserves every start and terminal result. Failed and interrupted attempts are never automatically retried or excluded. Missing usage remains incomplete; uncertain token reservations are not measured extra consumption.
- The Python viewer server is loopback-only and read-only. It validates local result hashes, confines file access, and renders saved text as text. It provides no editing or rerun endpoints. The Vercel deployment is a separate static snapshot of committed exports.

## Project records

- [Post-study audit](docs/POST_STUDY_AUDIT.md), [completion report](docs/COMPLETION_REPORT.md), and [implementation plan](docs/PLAN.md)
- [Held-out design](docs/HELDOUT_DESIGN.md), [evaluation report](docs/HELDOUT_EVALUATION.md), and [result export](docs/studies/heldout-v1-results.json)
- [Study runner](docs/STUDY_RUNNER.md), [viewer](docs/VIEWER.md), and [Ollama setup](docs/OLLAMA.md)
- [72-trial development pilot](docs/DEVELOPMENT_PILOT_72.md) and [matched fault pilot](docs/FAULT_PILOT_72.md)
- [Typed-log pilot](docs/LOG_CONTRACT_PILOT.md), [fixed-context smoke](docs/FIXED_CONTEXT_PILOT.md), and [60-trial consistency check](docs/FIXED_CONSISTENCY_60.md)
- [Execution policies](docs/POLICIES.md), [token-repetition diagnosis](docs/REPETITION_DIAGNOSIS.md), and [design review](docs/REVIEW.md)

Earlier development datasets retain their original policy versions and are not pooled with the held-out study. Disposable patch-review workspaces and broader benchmark replication are optional future work, separate from the delivered read-only lab.

Released under the [MIT License](LICENSE).
