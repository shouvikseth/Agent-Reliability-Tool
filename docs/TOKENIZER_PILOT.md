# Fingerprinted tokenizer admission pilot

Implemented opt-in `qwen-tokenizer-v1` in the Ollama adapter, CLI, and development pilot. The byte-based default is unchanged. Source was frozen at commit `6b930bb` before trial execution.

## Safety and calibration

The mode verifies a pinned tokenizer file SHA-256, Qwen 7B model digest, and installed chat-template hash before generation. It renders the validated system/user ChatML layout, reserves counted input plus 64 tokens of safety allowance, and sets output capacity from remaining aggregate/context budgets. It compares reported input usage exactly against its expected count before executing actions. Count mismatch is recorded as an infrastructure-invalid result with usage retained. An incompatible model/template prevents generation.

Additional calibration found a Unicode counterexample: expected 41, Ollama reported 42. Empty input (27), special-token text (35), and long ASCII input (747) matched. This counterexample is preserved in [tokenizer-calibration.json](pilots/tokenizer-calibration.json), not removed as an inconvenient result. Therefore only ASCII prompts use this tokenizer mode; non-ASCII prompts visibly fall back to `message-bytes-v2`. The installed Hugging Face tokenizer is not claimed universally equivalent to Ollama's tokenizer. `context_accounting` records each actual admission policy.

All 59 automated tests passed, including Docker integration, fingerprint rejection before generation, usage accounting on count mismatch, and explicit Unicode fallback without invoking the unsupported counter.

## Live development pilot

Command:

```powershell
.\.venv\Scripts\python -u -m lab.pilot --tokenizer-file diagnostics/qwen-tokenizer.json
```

All 12 scheduled trials have result records. Four development tasks ran once under three architectures in seeded block order, with identical 24,000 aggregate tokens, 20 tool calls, 600 seconds, 8192 context, 1024 output limit, local model digest, container image, seed, prompts, and tool policies. No other live inference diagnostics ran during this pilot.

| Task | Fixed | Single | Team |
| --- | --- | --- | --- |
| Pagination offset | Verified | HTTP 500 | Verified |
| Blank title | Verified | Defect check failed | Verified |
| Repeated closure | Verified | Empty-turn stop | Defect check failed |
| Request-key conflict | Verified | Empty-turn stop | Verified |
| Verified / scheduled | 4/4 | 0/4 | 3/4 |

Seven verified completions, two defect-check failures, two empty-turn stops, and one infrastructure-invalid HTTP 500 account for the scheduled trials. No run stopped for context admission. All 36 completed model responses matched expected input tokens. All 37 attempted generations used ASCII tokenizer admission; the failed HTTP request had no reported usage and retained its uncertain token reservation. Model API fees were zero; hardware/electricity costs were not measured.

Outcomes and reproducibility metadata: [tokenizer-admission-v1.json](pilots/tokenizer-admission-v1.json). Local complete traces: `runs/pilot-005fcf613e8d46feaed765d2f21804f7/`. Earlier baselines and failures are preserved. Do not pool versions or claim a general architecture ranking from these tuned, single-repetition development results. This pilot supports improved admission behavior on the tested inputs, not a causal repair-quality claim.

## Remaining gate

The Ollama HTTP 500 persists; tokenizer admission does not fix it. Capture an exact request artifact at dispatch and a sanitized server diagnostic, then compare isolated warm/cold repetitions before the 72-trial expansion. Continue to record linked infrastructure-invalid attempts rather than silently retrying. Unicode tokenizer equivalence and larger-template/multi-message layouts remain unsupported; retain fallback and fingerprint checks.

Setup and invocation are documented in [OLLAMA.md](OLLAMA.md). No server update, model-weight replacement, budget increase, or hidden-test exposure was introduced.
