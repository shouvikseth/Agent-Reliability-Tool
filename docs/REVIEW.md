# Proposal review

The proposal correctly separates patch submission from independent grading, shares aggregate resources across roles, and treats repeat runs as dependent observations. Keeping negative results and raw counts will make the study useful even if simpler control flow wins.

Before freezing the study, resolve these details:

1. Enforce isolation in both execution and grading. Workspace-only path checks cannot sandbox Python. Use fresh non-root containers with no network, a read-only base, no host socket or credentials, bounded writable storage, PID/memory/CPU limits, and process deadlines. A malicious patch must not read verifier files; execute hidden tests through a trusted external boundary or document the weaker threat model explicitly.
2. Preflight dependencies and container health before scheduling. Pytest collection failures and missing dependencies are infrastructure failures; assertion failures and candidate-caused import errors are patch failures. Record original attempts and exclusions, never overwrite them.
3. A fault rule only applies when its tool is invoked. Log eligibility and actual triggering separately. The primary analysis should include all assigned runs; a triggered-only secondary analysis is selection-biased. Include useful logs in all task inputs so log reads are plausible without forcing identical tool behavior.
4. Define budget reservation before model requests. Token/cost counters checked after a response measure overshoot but do not enforce a hard cap. Reserve worst-case output cost, set provider output limits, propagate deadlines, and reconcile measured usage across every role and retry.
5. Freeze model ID, prices, prompts, container digest, manifests, test hashes, and code commit in a versioned study manifest. A provider's seed is metadata, not reproducibility assurance.
6. Split public regression coverage from private defect checks. Confirm all regression checks pass at every seeded starting state. Prevent candidate edits to public tests from influencing grading.
7. Keep held-out tasks unwritten until orchestration is tuned on development tasks. All eight current tasks are explicitly development tasks. Twelve distinct tasks remain to be authored and frozen; do not relabel development variants as independent held-out evidence.

The first useful milestone is a validated CLI pipeline. A viewer adds value after real traces and outcome schemas stabilize. The current implementation deliberately exposes its incomplete provider/isolation boundary instead of claiming benchmark results from a scripted fixture.
