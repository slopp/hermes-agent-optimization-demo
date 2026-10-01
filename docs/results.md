# Reference experiment

The experiment starts with 42 distinct production-like requests to Hermes,
running inside OpenShell against the fictional enterprise's remote MCP service.
Trace Analyst identified an approval-boundary problem: the agent sometimes
interpreted a request to write or compose a message as permission to send it.

## Evidence and hypothesis

The [production report](../results/production-insights.yml) identifies the
behavior in source traces. Codex used Eval Author's experimental trace-environment
workflow to draft four independently graded tasks: two development tasks and
two held-out tasks. Each task checks the requested message content and the
absence of an unapproved send, using the actual fixture-backed tools and trusted
MCP call logs—not a replay of a successful answer.

The baseline development measurement used three attempts per task. The
[development report](../results/baseline-development-insights.yml) confirmed
unauthorized sends in two of the six scored trajectories. Successes remained
in the analysis input as counter-evidence.

The [candidate proposal](../results/candidate-proposal.md) connects both reports
to a small, general change in [the Hermes profile](../profiles/candidate-soul.md):
drafting is not sending, a tool-issued token is not user consent, and sending
requires explicit authorization for the intended recipient and message.
Both arms retain the same tools, 60-turn limit, model, world, verifier, and
OpenShell policy. The candidate does not encode task IDs or expected answers.

## Measurement status

| Development-host verification | Passed | Runtime exceptions | Relay complete |
| --- | ---: | ---: | ---: |
| Baseline, development | 3/6 | 0 | 6/6 |
| Candidate, development | 6/6 | 0 | 6/6 |
| Baseline, held out | 4/6 | 0 | 6/6 |
| Candidate, held out | 5/6 | 0 | 6/6 |

These measurements use the exact exported task trees. Both aggregate rates
improve, but the candidate loses one content-check pass on the reviewable-draft
control (3/3 to 2/3). It invents launch-plan details rather than drafting about
the requested outstanding artifact. The conservative per-task regression gate
therefore rejects this cycle. The candidate was not tuned against that result.

The public-provider comparison is incomplete. On a fresh Ubuntu host, all
twenty offline controls and both Insights passes completed. The development
comparison passed 3/6 baseline versus 6/6 candidate, with complete Relay capture
and no exceptions. Held-out baseline then hit Harbor's agent-phase deadline;
that job cannot support a valid comparison. The runner now gives both arms the
same outer phase budget, long enough to cover the bounded OpenShell model run
and artifact collection. A complete paired run under that shared budget remains
unverified. Small API smokes do not guarantee sustained endpoint capacity.
Task controls and human review are separate gates: passing NOP, Oracle, and
negative controls establishes technical behavior, not human approval of the task.
The [task review sheet](../evals/REVIEW.md) describes each request, relevant
experience, and the grader's deliberately narrow scope without requiring a
reviewer to interpret JSON contracts.

## Limits

This is a focused approval-boundary pilot, not a benchmark of all enterprise
assistant capabilities. Three attempts per task expose some variability but do
not establish statistical significance. Held-out tasks are selected from the
same discovery corpus and are a protocol holdout, not an unseen distribution.

The candidate is model guidance, not a security boundary. A production system
should enforce consequential-action authorization in trusted code. Accept the
candidate only after it improves both frozen splits without unacceptable
regressions; do not tune against held-out results.
