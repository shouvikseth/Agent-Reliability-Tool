# OpenAI adapter validation

Implemented a pinned OpenAI Responses adapter and `run` CLI command. The optional dependency is `openai==3.42.0`. Generation uses the host credential, official API endpoint, standard service tier, strict function-call actions, disabled automatic retries, input-token preflight, shared budget reservation, and a run deadline.

Validation: 27 tests passed with `LAB_DOCKER_TESTS=1`. Coverage includes the installed SDK with mocked HTTP, cached input pricing, preflight refusal, shrinking output limits, invalid action rejection, incomplete-response usage, transport failure accounting, deadline cancellation, shared team usage, CLI setup failures, and a mocked single-agent repair verified through Docker. Existing isolation checks also passed.

No live API request was made. The SDK was installed, but `OPENAI_API_KEY` was absent from the Codex process. The user's PowerShell environment may contain it; that shell can run the pilot command in README.md. Account access, live provider response behavior, latency, actual repair quality, and billed costs remain unverified.

Default pilot model: `gpt-5.4-mini-2026-03-17`. Standard text rates: $0.75 input, $0.075 cached input, $4.50 output per million tokens, checked October 30, 2026 against [the official model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Rates are local accounting configuration, not a provider-enforced account spending cap. Model access depends on the user's project.

On ambiguous transport failures, the result retains the request's maximum reserved allowance and marks actual total cost unknown. A locally cancelled request can continue remotely; reconcile provider billing before reporting costs. These tests establish the adapter contract and isolated workflow, not benchmark performance.
