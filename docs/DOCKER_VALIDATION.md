# Docker milestone validation

Validated on Docker Desktop's Linux engine, Docker 29.8.2, from Windows PowerShell.

Commands:

```powershell
docker build -f docker/Dockerfile -t agent-reliability-lab:dev .
$env:LAB_DOCKER_TESTS = '1'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m lab.cli validate --backend docker
.\.venv\Scripts\python -m lab.cli smoke --backend docker --architecture fixed --fault timeout
```

Results: 12 tests passed. All eight development tasks validated: seeded versions fail their external defect checks and pass regression; reference fixes pass both. Integration checks cover non-root execution, read-only root, network denial, no host mounts/socket, resource settings, deadline termination, and container cleanup.

The scripted timeout smoke run submitted an unchanged patch, recorded the injected fault, failed defect verification, and passed regression. This is the expected fixture outcome and is not an LLM benchmark result. Its local output is `runs/8d7d2192c22443868275a0ebb4141f1e/`; runs are git-ignored. Image identifier: `sha256:3313f675a54b8801aa69fdd15a061adeee3922c1613dcccf72d52b94859c1676`.

The cleanup test uses a backend-specific label so independent concurrent runs do not affect its assertions. Docker control-plane errors propagate separately from failed candidate API checks. A model provider, pre-request budget reservations, full infrastructure classification, and held-out tasks remain future work.
