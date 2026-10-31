# Agent Reliability Lab

A reproducible study of fixed workflows, single agents, and planner/writer/reviewer orchestration for software repair.

**Current state: development pilot, not a completed benchmark.** Ten development defects, an SQLite-backed FastAPI target, three orchestration contracts, narrow tools, fault injection, Docker execution, external API verification, model adapters, JSONL traces, SQLite results, and a deterministic 216-run schedule design are implemented. `smoke` uses a scripted no-op fixture; `run` uses a real provider. Smoke failures are expected and are not experimental results.

The new [typed-log pilot](docs/LOG_CONTRACT_PILOT.md) uses a validated `logs-v2` response envelope and two log-informed development tasks. All six malformed assignments triggered; four runs regained valid log access, but only one verified a repair. This separate pilot does not replace the earlier 144-run baseline. All 77 automated tests passed.

Current fixed workflow: [bounded context acquisition](docs/FIXED_CONTEXT_PILOT.md) reads source and logs deterministically, retries one eligible log-decoding error, then uses patch and revision model stages. All 82 tests passed. Its separate four-run smoke check verified 1/2 clean and 1/2 faulted repairs; the old datasets are preserved under their original policy versions.

The [60-trial fixed-workflow consistency check](docs/FIXED_CONSISTENCY_60.md) is complete across all ten development tasks: 23/30 verified clean and 23/30 with assigned faults. All 30 faults triggered, and all 18 malformed-log runs regained valid context with one retry. One faulted patch failed regression checks. All 83 automated tests passed, including Docker integration. This development result does not establish held-out performance; held-out tasks and the trace viewer remain future work.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m lab.cli validate
.\.venv\Scripts\python -m lab.cli smoke --architecture fixed --fault timeout
.\.venv\Scripts\python -m lab.cli schedule > schedule.json
```

`validate` checks that each seeded task fails its independent defect test, passes its public regression test, and passes both after applying the reference fix. `smoke` persists `events.jsonl`, `patch.diff`, `result.json`, and a SQLite row beneath `runs/`. `schedule` produces a design with placeholder held-out IDs; those tasks do not exist yet.

## Real OpenAI pilot

For a local model without API fees, see [the Ollama setup guide](docs/OLLAMA.md). Both providers use the same restricted tools and Docker grader. Report provider-specific experiments separately.

Optional Qwen tokenizer admission is available with `--tokenizer-file diagnostics/qwen-tokenizer.json`. It checks the tokenizer/model/template fingerprints and uses conservative fallback for non-ASCII prompts. See [setup](docs/OLLAMA.md) and the [12-trial integration pilot](docs/TOKENIZER_PILOT.md); the default byte-admission baseline remains available.

Local generation requests are now captured byte-for-byte under each run's `requests/` directory for diagnostic replay. The previously unexplained HTTP 500 was reproduced as a token-repetition abort; [diagnosis and bounded handling](docs/REPETITION_DIAGNOSIS.md) document the evidence, revised failure classification, and remaining limitations.

The [72-trial clean development pilot](docs/DEVELOPMENT_PILOT_72.md) is complete: fixed 18/24, single 8/24, team 17/24 verified completions. All outcomes, per-task consistency, failures, and limitations are published. This is development evidence, not a held-out benchmark or general architecture ranking. `python -m lab.report <pilot-directory> --output <new-json-file>` validates schedule completeness and regenerates aggregates without overwriting earlier exports.

The [matched fault pilot](docs/FAULT_PILOT_72.md) adds 72 trials: fixed 18/24, single 8/24, team 15/24 verified. Only 30 assigned faults triggered (28 timeouts, two corrupted log reads), so assignment and exposure are reported separately. Use `python -m lab.pilot ... --condition injected` to reproduce the stable canonical task-level assignment. Log-content corruption is not a transport-envelope fault; the report documents this limitation and the next validation gate.

To run the balanced local development pilot (four development tasks, all three architectures, clean tools, one repetition each):

```powershell
.\.venv\Scripts\python -u -m lab.pilot
```

This runs 12 sequential GPU trials with identical budgets. It freezes a seeded architecture order in `schedule.json`, records the source commit, and appends outcomes to `summary.jsonl` under a new `runs/pilot-*` directory. Per-run manifests, traces, diffs, grading, and SQLite results are preserved. It never uses a paid provider or held-out tasks. `--repetitions 2` or `3` broadens development consistency checks; it does not make this a held-out study. Current rules are `completion-v5` and `bounded-actions-v4/fixed-context-v1/logs-v2`, with deterministic fixed-workflow context acquisition, stage-specific instruction hashes, bounded actions, passed-test caching, empty-turn feedback, and revised local context admission. Use `--architectures fixed` to scope a development check; the default still runs all three architectures. See [execution policies](docs/POLICIES.md); v3 reports describe the prior baseline.

Install the optional SDK dependency once:

```powershell
.\.venv\Scripts\python -m pip install 'openai==3.42.0'
```

In the same PowerShell window where you will run the pilot, set `OPENAI_API_KEY` without putting the key in command history:

```powershell
$secret = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
Remove-Variable secret
```

With the Docker image built, run one development task:

```powershell
.\.venv\Scripts\python -m lab.cli run --provider openai --backend docker --model gpt-5.4-mini-2026-03-17 --task pagination-final --architecture single --max-dollars 0.25 --max-tokens 24000 --max-output-tokens 2048 --max-seconds 180 --max-tool-calls 20
```

This sends paid generation requests. The default model is a pinned GPT-5.4 Mini snapshot. Stored standard rates are $0.75 input, $0.075 cached input, and $4.50 output per million tokens, checked October 30, 2026 against [OpenAI's model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Verify rates before a study; the local dollar limit relies on these rates, standard service tier, and the configured endpoint. Unknown model IDs are rejected until their pricing is explicitly added. Account access to this snapshot is not guaranteed.

The adapter uses a strict `respond` function to return visible status and ordered restricted actions. It never executes provider-supplied code on the host. All roles share a usage ledger. Before each generation, the [input-token endpoint](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count) counts the exact request, then the adapter reserves uncached input cost plus the maximum permitted output cost. Output limits shrink to remaining token/dollar capacity; requests with insufficient capacity do not generate. Automatic SDK retries are disabled. A single deadline covers token counting and generation. No private reasoning items are logged or resent.

Each run stores `manifest.json`, `events.jsonl`, `patch.diff`, and `result.json` beneath its printed output directory, plus a SQLite result. Usage includes failed/incomplete responses whenever reported. After transport failure or cancellation, billing can be uncertain: `dollars` is null, `known_dollars` retains reported charges, and `uncertain_reserved_*` retains the unresolved allowance. The adapter stops; it never treats missing usage as a free request or automatically retries. Cancelling a local request cannot guarantee the remote service stops billing immediately. Reconcile such runs against provider usage records before cost reporting.

Exit code 0 means independently verified completion; code 1 means the saved run did not complete successfully; code 2 means invalid CLI setup. Inspect `status`, `error`, `verification`, and `usage_complete` in the saved result. `run` refuses the host/local backend. Changing `--architecture` to `fixed` or `team` keeps the same provider and aggregate resource settings. Use `--fault timeout` for the next pilot after a clean attempt. Only development tasks are currently available.

Common setup errors: `OPENAI_API_KEY` missing means set it in this same shell; HTTP 401 means check the key; HTTP 403/404 can indicate model/project access; HTTP 429 can indicate quota or rate limits. Raw provider errors and headers are not saved, so investigate account details in the provider dashboard. Docker image errors require building the image above. Do not share the key in chat; the SDK runs on the host and keys are never transferred into containers.

## Target API

- `POST /issues`: JSON title, optional `request_key` query parameter. Replays return the original ID; conflicting reuse returns 409.
- `GET /issues`: offset, limit, optional open/closed state; deterministic ID order.
- `POST /issues/{id}/close`: open to closed, 404 for missing issues, 409 for repeated closure.

## Execution boundary

### Docker backend

With Docker Desktop's Linux engine running:

```powershell
docker build -f docker/Dockerfile -t agent-reliability-lab:dev .
$env:LAB_DOCKER_TESTS = '1'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m lab.cli validate --backend docker
.\.venv\Scripts\python -m lab.cli smoke --backend docker --architecture fixed --fault timeout
```

The build context allows only `docker/`; no source tasks, credentials, or reference files enter the image. Each invocation transfers a bounded candidate source file and, for public testing, the canonical public test through stdin into a 32 MB temporary filesystem. Containers have no host mounts, published ports, Docker socket, or external network. They use UID 10001, a read-only root, dropped capabilities, no-new-privileges, 256 MB memory, one CPU, and a 64-process limit. These are Docker's standard [runtime restrictions](https://docs.docker.com/engine/containers/run/).

Public pytest execution and each independent grading phase use fresh containers. Hidden checks run in the host orchestrator against JSON-encoded API responses over stdin/stdout; candidate application source is never imported on the host. No verifier source, expected outcomes, or reference patches are transferred. Candidate code sees requests made to its API, as any service would. Public-test results are advisory; external checks determine completion. Container image IDs are recorded with smoke results. Test and API deadlines terminate the candidate; Docker setup/cleanup operations have separate bounded control timeouts, so total duration can exceed the candidate deadline during provisioning or cleanup.

This is a local research isolation layer, not a hardened multi-tenant service. Candidate code shares a process with the in-container API adapter and can tamper with its own response stream; checks evaluate those responses externally. Containers still depend on Docker/kernel isolation. Infrastructure errors are surfaced separately, and cleanup failures are errors rather than silent success.

### Local development backend

**Local tools and graders execute trusted Python code directly on the host. They are development utilities, not a security boundary. Do not attach a live model or run untrusted patches with this backend.** Paths and commands are restricted by the tool API, but candidate Python can still access the host. The grader rebuilds a clean temporary directory with only candidate application code and author-owned tests. This provides logical test separation, not isolation against malicious code.

Reference mutations and verifier generation live in `lab/tasks.py`, outside generated workspaces. Never expose this repository or `lab/` to the runtime agent. The Docker backend transfers only allowlisted file content; it does not mount the workspace.

See [implementation plan](docs/PLAN.md) and [design review](docs/REVIEW.md).
