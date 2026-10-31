# HTTP 500 reproduction and bounded handling

## Confirmed mechanism

An exact-wire capture of a fresh `pagination-offset` single-agent run reproduced HTTP 500 on request seven. Ollama 0.40.13's response was `prediction aborted, token repeat limit reached`. The request had 1702 prompt tokens in an 8192 context. The trace shows a failed replacement followed by repeated reads of identical source.

Three isolated replays of the same seventh-request file succeeded. Replaying all seven captured request files in order reproduced the repetition abort in both a warm sequence and a cold sequence after unloading only the project's Qwen model. Both failures had the same response-body hash. This demonstrates why reconstructing just the last request was insufficient. The diagnostic attempt remains separate from the original failure.

Evidence and linked outcomes: [repetition-diagnostics.json](pilots/repetition-diagnostics.json). The exact failed request hash is `a6b772cedd1ddceb3acad080a383b69e14ceac98670e92bbd9af9dddbed32be7`. Full raw requests remain local in `runs/c8acad95134240b6948da2831b96bf7b/requests/` and are not included in the public report.

Upstream context: [Ollama issue 8786](https://github.com/ollama/ollama/issues/8786) discusses output-token repetition; [issue 17270](https://github.com/ollama/ollama/issues/17270) reports a version-sensitive Windows case. These reports do not prove our underlying cause. Sequence sensitivity could involve model/backend/cache interaction. We have identified the immediate termination reason, not proved a general server root cause or a universally effective model repair.

## Implementation

Each local generation now saves the exact serialized request bytes that are sent, with artifact path, SHA-256, size, stage, and timestamp in the trace. No request headers or credentials are captured. These files contain candidate source and visible history, so they remain under git-ignored local run output. HTTP diagnostics retain a fixed recognized category, status, response digest, and byte count rather than arbitrary server text.

The known `token repeat limit reached` response is classified as `agent_error` / generation failure under the new handling, with its maximum token reservation retained because Ollama reports no usage on that error. Unknown HTTP errors remain infrastructure-invalid. This conservative counting policy does not prove the backend is blameless: it avoids excluding a known generation failure as if it were an unrelated outage. Previous raw statuses are unchanged and must not be pooled with the revised taxonomy without an explicit annotation.

`bounded-actions-v2` stops a run on its third request for the same read/log content and path before another model generation. A successful edit resets these observation counts. This policy is common across architectures and does not silently submit a patch or turn failure into success. It can stop potentially useful repeated inspection and must be included in the frozen tool contract.

Fresh guarded run `1e5dd64dfa09421692338599c20faed7`: 4 model requests, 4086 reported tokens, complete usage, no HTTP failure, and explicit unchanged-read `agent_error`. It remains an unsuccessful, unsubmitted repair. The corresponding unguarded run used 7 requests before the server abort and had incomplete usage. This is one diagnostic example, not a general effectiveness claim.

All 64 automated tests passed, including Docker integration, exact capture serialization, safe error classification, repetition failure accounting, and bounded read loops. Neither the server repetition guard nor the model weights, temperature, context size, or software version was changed.

## Reproduce safely

Replay a locally captured request without grading or changing any outcome:

```powershell
.\.venv\Scripts\python -m lab.replay runs/<run-id>/requests/request-0007.json --output diagnostics/new-replay.jsonl --repetitions 3
```

The output file must be new. Replays use only localhost, fixed local Qwen 7B, no proxies, no API key, and at most five repetitions. The sequential warm/cold diagnostics were performed while no benchmark inference was active. They were not counted as benchmark trials.

Next: freeze this revised contract and run the expanded development pilot with repetitions. Keep generation failures, incomplete usage, and all linked diagnostic/exclusion records visible. A controlled Ollama-version comparison remains optional if backend sensitivity needs investigation; no automatic software downgrade or blind retry was introduced.
