# Frozen study runner and durable attempts

The study runner adds the controls required to execute the separately validated held-out design. It uses local Ollama and Docker only. Preparation checks metadata and a trusted reference application; it sends no generation request. The original validation artifact remains unchanged.

All **100 automated tests passed** with Docker integration enabled. Fifteen new cases cover committed starts, preserving failures, recovery after a saved-result crash, interrupted attempts, duplicate rejection, artifact identity and completion checks, immutable records, concurrent locking, read-only status, source/design/environment drift, and local metadata-only provider preflight. Crash recovery tests use synthetic temporary results and make no held-out model requests.

The first live preparation passed at source commit `9130c42be4ed6458c04affa8393004c411c74fe2`. The [preparation evidence](studies/heldout-v1-preparation.json) records manifest/code fingerprints, observed versions and model/image fingerprints, and **216 pending slots with zero starts**. The complete frozen manifest and ledger remain local under `runs/heldout-v1/`. This evidence contains no evaluation outcomes. Environment versions reflect the installed host environment, including AnyIO 4.15.1; the project dependency declaration currently pins 4.9.0. Resume requires the observed frozen environment rather than assuming those versions coincide, and the host environment differs from the isolated image.

## Prepare and inspect

From a clean, committed checkout, with Docker and Ollama running and the pinned tokenizer installed:

```powershell
.\.venv\Scripts\python -m lab.study prepare --directory runs/heldout-v1 --tokenizer-file diagnostics/qwen-tokenizer.json
.\.venv\Scripts\python -m lab.study status --directory runs/heldout-v1
```

Preparation refuses an existing directory. Use a new name to reproduce preparation rather than overwriting an earlier study. It verifies every task/test fingerprint and mechanical check, the complete schedule, current configuration, installed model digest and template, tokenizer file, immutable Docker image, and a reference public test in Docker. Ollama calls are limited to loopback `/api/tags`, `/api/show`, and `/api/version`; proxy environment settings are disabled. It records Python, OS, Docker engine, Ollama, and dependency versions.

The manifest freezes normalized runtime source hashes, the source commit, the full validated design and its digest, expected configuration, and observed preflight metadata. It is bound to the SQLite ledger as a complete canonical JSON value. Later documentation commits can differ from the recorded source commit, but changing a runtime source file fails the hash check. Changing design, configuration, model fingerprints, or recorded environment versions stops a run before new attempts start.

`status` opens the ledger read-only and remains available while a runner is working. The summary accounts for all 216 scheduled slots, including pending, active, finished, and interrupted attempts. It reports candidate and infrastructure statuses, incomplete usage, verified completions, and zero exclusions. It does not present pending trials as successful or discard unsuccessful attempts.

## Execution and resume

After preparation, this command starts at most one previously unstarted slot:

```powershell
.\.venv\Scripts\python -u -m lab.study run --directory runs/heldout-v1 --tokenizer-file diagnostics/qwen-tokenizer.json --limit 1
```

The default limit is one; `--limit 216` allows the runner to process all remaining slots. Running the same command again resumes pending slots. Each run repeats preflight, compares its environment to preparation, and acquires an operating-system lock for the entire batch. A second runner or reconciliation command cannot operate concurrently; process death releases the lock even though the lock file remains.

The ledger commits a unique execution ID and start event before calling the existing isolated execution/grading pipeline. Slots retain the design's stable IDs, and each execution has a separate directory under `executions/<execution-id>/<run-id>/`. SQLite transactions, foreign keys, uniqueness constraints, full synchronization, and update/delete rejection protect the application-level append-only record. This is an audit mechanism for cooperating runners, not protection against an owner deliberately modifying the database.

Every finished result retains its JSON, artifact path and SHA-256. Identity, architecture, condition, image, backend, shared budget, policy, and independent completion flag are checked before recording it. Candidate failure, budget exhaustion, and infrastructure-invalid results all remain terminal outcomes. They are never automatically retried or excluded. Run-level provider metadata and traces remain in the original artifacts.

On resume, an unfinished start with one valid durable `result.json` is finalized with `recovered: true`. An unfinished start without a final result becomes `interrupted`, with incomplete usage and no verified completion. Any partial `execution.json` artifacts are preserved and hashed. Duplicate, contradictory, malformed, or mismatched result artifacts stop reconciliation for investigation. No attempt is overwritten or silently replaced.

Reconciliation can also be invoked without generating or preflighting a model:

```powershell
.\.venv\Scripts\python -m lab.study reconcile --directory runs/heldout-v1
```

Interrupted slots are not returned to the pending queue. There is currently no replacement-attempt or exclusion command. A future replacement policy would need an explicit audit relationship and separate analysis; it must not remove original failures. Local generation may continue on the Ollama server after a client interruption, so a reconciled record does not prove that server computation stopped.

## Before interpreting outcomes

Preparation is not an evaluation result. Held-out model requests must remain zero until the runnable configuration is frozen and checked. Once evaluation starts, do not tune prompts, tasks, architectures, model settings, or budgets from its outcomes. Preserve assigned versus triggered faults, regressions, all failure statuses, and incomplete usage in the final report. The task catalog is small and shares one application; repetitions are dependent observations. API fees are zero for the selected local provider; hardware/electricity costs are not measured.
