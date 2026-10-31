# Development execution policies

Current revision: `bounded-actions-v4/fixed-context-v1/logs-v2` adds predetermined source/log acquisition to the fixed workflow, with one retry only for a retryable log-decoding error. It replaces model-selected inspection and leaves two fixed-workflow model stages. Every acquisition call uses the common budget. See [design and smoke evidence](FIXED_CONTEXT_PILOT.md); earlier definitions below describe preserved baselines.

Update: `bounded-actions-v2` additionally stops the third read/log request for the same unchanged path/content; successful edits reset observation counts. Known Ollama token-repetition aborts now count as generation failures with uncertain token usage retained. See [the exact-wire reproduction](REPETITION_DIAGNOSIS.md). The v1 definition below remains the baseline for prior reports.

These policies replace the v3 pilot's behavior only in new runs. Old traces and outcomes remain intact. All architectures use the same policies; no patch is submitted implicitly.

## bounded-actions-v1 / completion-v4

Each model response may request at most six actions, enforced in the generation schema, decoder, and runtime before any action in an oversized batch executes. The common aggregate tool limit remains 20. Passing public test results are cached by candidate source SHA-256 for the lifetime of a run. Cache hits are visible to the model, logged, and still consume a tool call. Changed source forces a new test. Failed tests, pre-execution injected faults, and timeouts are not cached. Independent grading always runs fresh and never uses this cache.

A single agent's first empty turn receives explicit runtime feedback. A second consecutive empty turn stops as `agent_error`; neither is treated as submission. Final fixed/team revision stages may return empty actions and retain orchestrator-controlled submission.

## visible-history-v1

Both providers receive all visible action records and tool statuses. Model commentary is clipped to 160 characters, test output to its last 2000 characters, and repeated identical read/log content is replaced by a SHA-256 marker pointing to the latest full copy in the history. Source and edit arguments are not paraphrased. Original history is not modified, and complete originals stay in JSONL events. This is deterministic lossy context compaction, not a claim of semantic equivalence: clipped commentary or test output can omit useful details.

## message-bytes-v2 (Ollama admission)

Local admission reserves the sum of actual system/user message UTF-8 bytes plus 512 tokens of template allowance, then bounds output by remaining aggregate tokens and context. It no longer includes the decoding grammar schema or a second JSON escaping layer as prompt text. Ollama's [prompt implementation](https://github.com/ollama/ollama/blob/main/server/prompt.go) renders messages and tools into a prompt; the separate `format` schema is not sent as a tool here. See [the native chat API](https://docs.ollama.com/api/chat) for format and reported usage fields.

`context_accounting` records original/visible history size, admission allowance, and permitted output. `context_measurement` records actual prompt tokens and unused reservation. The allowance remains conservative and approximate, not tokenizer-exact. Any observed reservation overage stops before actions execute and is retained as failure. OpenAI keeps its exact provider input-token preflight. Local and hosted admission policies therefore differ.

The changed policies and completion instructions must be frozen before another comparison. Do not merge outcomes from different versions into one reported controlled experiment. Development pilots can guide changes; held-out outcomes cannot.
