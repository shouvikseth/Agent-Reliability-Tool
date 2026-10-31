# Typed logs and log-informed development pilot

The existing 144-run baseline is unchanged. New runs use `completion-v5` and `bounded-actions-v3/logs-v2`, frozen at commit `6d70604`. Two additional development fixtures bring the pool to ten. No held-out tasks were created or relabeled.

## Boundary contract

The log producer serializes a JSON envelope with exactly `schema: logs-v2`, `ok: true`, and string `content`. A decoder validates syntax, keys, and types. Invalid wire JSON or schema produces `ok: false` with code `invalid_log_response` and `retryable: true`. Invalid content is not forwarded as application evidence.

The `malformed` condition now inserts invalid JSON before that decoder on the first log invocation only. Later log calls can succeed and still consume budget. This simulates a producer/consumer decoding boundary, not a real network failure. The decoder validates; the model chooses whether to retry its tool. No automatic retry or implicit submission is added. This is distinct from the older log-content corruption and must not be pooled with its results.

## Development fixtures and verification

`log-limit-zero` supplies a client log showing limit zero returning 200 despite a 1–100 contract requiring 422. The seed changes the lower bound from one to zero. `log-title-length` supplies a log showing a valid 21-character title rejected despite a 1–200 contract; the seed caps it at 20. Verification tests zero/one limits and title lengths 21/200/201.

Issue descriptions point to useful logs containing reproduction details and API requirements, without reference patches or verifier code. Tools remain optional; neither log access nor recovery earns grading credit. Direct file reads remain available. Docker validation confirmed both seeded defects fail independent defect tests, pass regression, and pass both after reference repair. All 77 tests passed, including invalid syntax/type/shape, exactly-once injection, retry success, and independent grading.

## Pilot results

Two tasks × three architectures × one repetition × two conditions produced 12 records. Seed, model digest, prompts, image, and budgets match across conditions: 24,000 tokens, 20 tool calls, 600 seconds, 8192 context, and 1024 output tokens. Inference was sequential, with no paid API or concurrent diagnostic inference.

| Task / condition | Fixed | Single | Team |
| --- | --- | --- | --- |
| Zero limit, clean | Failed verification | Budget stop | Failed verification |
| Title length, clean | Verified | Verified | Incomplete response |
| Zero limit, malformed | Failed verification | Failed verification | Repeated-observation stop |
| Title length, malformed | Failed verification | Budget stop | Verified |

Clean: **2/6 verified**. Malformed: **1/6 verified**. The fault triggered in **6/6** assigned runs. This selected fixture pilot achieved more log exposure than the earlier study, but changes to tasks, prompts, and contract prevent a controlled cross-version improvement claim.

Both single-agent runs and both team runs later obtained valid log envelopes: **4/6 recovered log access**, while only **1/6 verified a repair**. Neither fixed run retried logs; its later stages do not permit log calls. This makes the one-response inspection stage a limitation to examine before freezing. Do not discard failures or infer an architecture ranking from one repetition on two tuned tasks. The team's malformed-condition success after a clean failure is one pair, not causal evidence.

## Data and reproduction

- [Clean outcomes](pilots/logs-v2-clean.json)
- [Malformed outcomes](pilots/logs-v2-malformed.json)
- [Retry and valid-envelope counts](pilots/logs-v2-recovery.json)

Raw traces remain under `runs/pilot-f148fdba427446768eb76ab8c377de2b/` (clean) and `runs/pilot-75c8fec4303e40daad6581ffcd3df46c/` (malformed). Public exports exclude credentials and raw requests.

```powershell
.\.venv\Scripts\python -u -m lab.pilot --tasks log-limit-zero log-title-length --tokenizer-file diagnostics/qwen-tokenizer.json --condition clean
.\.venv\Scripts\python -u -m lab.pilot --tasks log-limit-zero log-title-length --tokenizer-file diagnostics/qwen-tokenizer.json --condition injected
```

Next: document bounded context-acquisition/retry rules for the fixed workflow, then retest under a new freeze if rules change. More repetitions are needed for consistency. Preserve this pilot separately from the 144-run baseline. Held-out authoring, final freeze, 216 held-out trials, and viewer work remain outstanding.
