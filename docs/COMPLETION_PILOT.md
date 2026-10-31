# Completion instruction development pilot

Shared completion rules now explicitly permit an empty action list when revision has nothing to change, discourage redundant tests, and distinguish orchestrator submission from single-agent submission. The rules are versioned as `completion-v2`. Both provider manifests record that version and the base prompt SHA-256. Runtime tests verify an empty revision preserves the patch and reaches submission without another test. All 40 unit/provider/Docker tests passed.

Retested `pagination-final`, clean tools, with Qwen2.5 Coder 7B digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. Every architecture received 20 tool calls, 24,000 aggregate tokens, 600 seconds, 8192 context, 1024 maximum output tokens, seed 20261030, and the same Docker image. Execution order was single, team, fixed. All runs incurred zero external API fees.

| Architecture | Verified completion | Seconds | Tokens | Run ID |
| --- | --- | --- | --- | --- |
| Single | No: conservative context allowance exhausted | 7.14 | 10,462 | 70b0d3f4a5b9408d973d21be5568c7c2 |
| Team | Yes: defect and regression checks passed | 9.36 | 4,125 | 57f4ee874c854460af51ce6489aa01ff |
| Fixed | Yes: defect and regression checks passed | 11.83 | 2,846 | 3dbd8afcc3b24e5ba20565763381f159 |

The single agent read and edited the application, then repeatedly returned empty action lists without testing or submitting. The no-change example appears to have influenced its completion behavior; this is an interpretation of visible output, not access to model reasoning. The team and fixed runs reached orchestrator submission and passed independent checks.

Earlier fixed/team failures and earlier single-agent successes remain intact in `runs/`. Do not combine versions into a controlled comparison or infer an architecture ranking from one tuned development task. No held-out tasks were used. Next development candidate: provide stage-specific completion instructions to reduce ambiguity, then evaluate across more development tasks with a fixed configuration and repetitions. Do not silently treat single-agent empty actions as submission; that would change the explicit submission contract.
