# Validated repair options for local execution

## Context accounting: replace bytes with the pinned Qwen tokenizer

The most practical fix is now experimentally supported. Downloaded only the official Qwen tokenizer (7,031,645 bytes; not model weights) at repository revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`. Its SHA-256 is recorded in [tokenizer-diagnostics.json](pilots/tokenizer-diagnostics.json). The upstream source is [Qwen's tokenizer configuration](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/blob/c03e6d358207e414f1eca0bb1891e29f1db0e242/tokenizer_config.json).

Read the installed Ollama model template through `/api/show`. For our two-message system/user layout with no native function tools, rendered the Qwen ChatML prompt and counted it using `tokenizers==0.22.2`. During an isolated seven-request replay, counts matched Ollama exactly: 299, 1076, 1177, 1309, 1440, 1571, and 1702. The last count also matches the original server log's failed request. This establishes compatibility on these inputs, not every model, template, or special-token edge case.

Added an offline diagnostic that checks the tokenizer hash and rejects unsupported layouts:

```powershell
.\.venv\Scripts\python -m lab.token_accounting diagnostics/failed-request.json --tokenizer-file diagnostics/qwen-tokenizer.json
```

The tokenizer and candidate-containing request are kept in git-ignored `diagnostics/`. Public diagnostic results contain counts/status only. The optional installation dependency is `local-tokenizer`; three new tests verify prompt rendering, supported layout restrictions, and hash rejection.

Recommended integration: add an explicit tokenizer admission mode; verify the installed model digest and template hash; reserve rendered prompt count plus a documented safety margin and output allowance; reconcile every response; fail before actions on count mismatch. Test Unicode, empty messages, special-token strings, and long histories first. Preserve `message-bytes-v2` as the baseline and label new runs with a different policy. The active runner is intentionally unchanged by this diagnostic-only investigation.

## HTTP 500: improve reproduction before changing the server

Ollama version is 0.40.13. Both original failures occurred after generation had started on a 1702-token prompt in an 8192-token slot. The nearby logs do not report an out-of-memory condition, invalid schema, or context overflow. A GPU discovery watchdog timeout exists elsewhere in the log, but it occurred earlier and is not evidence that it caused these failures.

Corrected an earlier replay omission: failed edit feedback must be included when reconstructing runtime history. Two isolated accurate single-request schema replays returned 200, as did a JSON-mode comparison. The entire original seven-request sequence also returned 200 at every step while no benchmark was active. These diagnostic responses do not replace or exclude the recorded HTTP 500 trial.

The failure remains unresolved and should not be described as fixed. The evidence does not support switching off structured outputs or increasing context as a proven remedy. Cache/runner state or nondeterministic backend behavior are hypotheses only.

Recommended next diagnostics: save the exact request hash and version/digest/template fingerprint at dispatch; capture the bounded, sanitized server error and corresponding log timestamps; run warm/cold sequence repetitions serially; compare another pinned Ollama version only as an explicit experiment with the ability to revert. Do not update the server, unload unrelated models, or introduce retries silently during a frozen evaluation. If infrastructure-invalid runs are retried later, append linked attempts and retain the reason; do not overwrite originals.

## Alternative if backend instability persists

An optional llama.cpp backend would expose its documented `/tokenize` endpoint and render chat templates within the same engine used for inference. This is a larger integration change and not installed here. See the [official server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Validate tool schemas and model/template fingerprints before comparing results across backends. The pinned local tokenizer is the smaller immediate change for this project.

This investigation used no paid API calls and changed no benchmark outcomes, prompts, budgets, model weights, server settings, or active admission defaults.
