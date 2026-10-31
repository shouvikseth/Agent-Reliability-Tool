# Local model setup with Ollama

This route uses the computer's own GPU and requires no OpenAI key or paid API credit. Hardware, power, disk, and time costs remain. The target application still runs in Docker; Ollama runs on the host and cannot give the application network access.

## Setup on this laptop

Observed hardware: 16 GB RAM, NVIDIA RTX 4070 Laptop GPU with approximately 8 GB VRAM. Start with `qwen2.5-coder:7b`, a 4.7 GB quantized coding model. This is a reasonable pilot candidate, not a measured speed or repair-quality guarantee. Close memory-heavy applications while running Docker and the model. Use `qwen2.5-coder:3b` if memory pressure is excessive, and label those results separately.

1. Download and install [Ollama for Windows](https://ollama.com/download/windows). It supports native NVIDIA acceleration; [Windows requirements](https://docs.ollama.com/windows) include a compatible driver. Start Ollama after installation, then open a new PowerShell window so its CLI is on PATH. No API subscription or cloud account is needed for the local model.
2. Download the model once (approximately 4.7 GB):

```powershell
ollama pull qwen2.5-coder:7b
```

3. Start Docker Desktop if it is not running. Then run the local pilot from the repository:

```powershell
cd "C:\Users\shouv\OneDrive\Documents\ChatGPT\agent reliability check"
.\.venv\Scripts\python -m lab.cli run --provider ollama --backend docker --model qwen2.5-coder:7b --task pagination-final --architecture single --max-seconds 600 --max-tokens 24000
```

4. To check whether Ollama is using the GPU while the model is loaded:

```powershell
ollama ps
```

If the CLI is not recognized, restart the terminal after installation. If the adapter says Ollama is unreachable, start the Ollama application. If the model is missing, run the pull command. To unload a model after use, run `ollama stop qwen2.5-coder:7b`.

## Runtime and limits

The adapter uses the local-only endpoint `http://127.0.0.1:11434`, ignores proxy environment variables, sends no API key, performs no automatic downloads or cloud fallback, and accepts only the two documented local Qwen tags. It uses Ollama's [JSON schema outputs](https://docs.ollama.com/capabilities/structured-outputs) for ordered actions, validates role permissions, and records the installed model digest. Context is 8192 tokens, output limit defaults to 1024, temperature is zero, and the CLI seed is recorded. These settings do not guarantee deterministic generation. Freeze model digests and the Ollama version before evaluation; tags can change.

Ollama has no exact input-token preflight in this adapter. Current `message-bytes-v2` conservatively reserves actual message UTF-8 bytes plus template allowance, excluding the decoding grammar and duplicate JSON escaping, then reconciles reported prompt/output counts. The shared visible-history policy shortens commentary/test logs and replaces duplicate file content with markers; full originals remain in traces. This is a conservative pilot estimate, not tokenizer-exact admission control; unexpected overages stop before actions execute. Long histories can exhaust this allowance before actual context is full. Different providers therefore have different admission policies and should not be presented as a controlled same-model architecture comparison. See [the policy pilot and limitations](POLICY_PILOT.md).

`dollars: 0.0` means no external model API fees, not zero electricity/hardware costs. Timeouts can leave the local Ollama server computing after the client disconnects; no new run should start until the prior request has stopped. Usage is marked incomplete when token counts are missing. Public tests and independent verification remain the same as for OpenAI.

Provider contracts are tested with mocked HTTP. A live development pilot subsequently passed external defect and regression verification for `pagination-final`, single agent, clean tools: run `606173b35a334391b9a822d6a8d21014`, 4 requests, 3897 tokens, approximately 14.5 seconds, zero external API fees. This is one development success, not held-out benchmark evidence.

An earlier development run (`c24dd1500a1045fa88e82007ce37b4ef`) found and edited the defect but failed action validation because the model supplied replacement arguments on a test call. The action schema was tightened to a per-tool union that constrains unused fields to null. Runtime validation remains strict, and the original failed run is preserved. Twenty-five provider tests passed after this correction.

Model source and download size: [Qwen2.5 Coder 7B](https://ollama.com/library/qwen2.5-coder:7b). Native request/usage schema: [Ollama chat API](https://docs.ollama.com/api/chat).
