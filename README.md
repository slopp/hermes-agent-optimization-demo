# Optimize a Hermes enterprise-agent harness with NVIDIA NeMo

This repository is a runnable tutorial for turning production-like agent traces
into a reproducible harness optimization:

```text
36 checked-in baseline traces
        │
        ├─ NeMo Insights → failure patterns and harness hypotheses
        │
        └─ Codex + Eval Author → 6 development Harbor tasks
                                      │
                         baseline Hermes ── candidate Hermes
                                      │
                              4 held-out tasks
```

Harbor runs both arms against the same task-local MCP server and fixture world.
The verifier scores the answer, actual MCP calls, retry budget, and mutation
state; those Harbor rewards—not a separate mock runner—are the A/B result.
NeMo Relay records every Hermes run for the next Insights pass.

You do not have to generate traces to start. The trace corpus, fictional world,
Eval Author-derived reference tasks, Hermes profiles, and controls are checked
in. Recollecting traces through NemoClaw is an optional deployment exercise.
NeMo Platform is not required.

## Production grounding

The problem shapes come from NVIDIA's optimization of Personal Assistant, an
internal production agent that helps employees research and act across email,
calendar, chat, files, enterprise knowledge, directories, and task systems.
The tutorial recreates those engineering challenges in a deterministic fictional
company called Northstar. NVIDIA's public
[Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes the related methodology.

Northstar is preparing a product launch. Its 504-record world includes current
and stale projects, ambiguous people, paginated results, a large JSON evidence
register, a disconnected CRM, and a transient incident-search failure.

| Fictional MCP surface | Typical enterprise equivalent |
| --- | --- |
| people, mail, calendar | Workday/Entra ID, Outlook/Gmail, enterprise calendars |
| chat, knowledge, files | Teams/Slack, Confluence/Glean, SharePoint/Drive |
| projects, analytics, support | Jira/Asana, BI platforms, ServiceNow/Zendesk |
| connectors, actions | integration health plus approval-gated draft/send APIs |

## What the evals exercise

The 36 starting traces are six trials from each of six behavior families.
Guided by Eval Author skills, Codex audits the pile and turns one reviewed
representative from each family into a development task; four paraphrases
remain held out until the final gate.

- Multi-source coverage: retrieve both a chat blocker and calendar review time.
- Search then read: open a selected thread before citing its messages.
- Bounded retry: repeat one transient call exactly, then use one declared fallback.
- Authentication awareness: report an unavailable connector instead of guessing.
- Approval boundary: prepare a message without sending it.
- Structured inspection: search for a large JSON record and read only `/evidence`.

The baseline has a broad built-in tool surface, a generic system policy, and a
60-turn budget. Its traces show source omissions, local/web detours, search hits
used without reads, guessed structured arguments, and loose retries. The
candidate applies the patterns those traces motivate: claim-to-source routing,
search-then-read, schema-first calls, exact retry transitions, bounded JSON
inspection, prepare-without-send, tool downsampling, and a 12-turn budget.

These are hypotheses to test, not universal defaults. The tutorial keeps the
model, task environment, fixtures, prompts, and verifiers fixed between arms.
On the clean reference run, the baseline passed 2/12 held-out trials and the
candidate passed 11/12; the [measured result](docs/results.md) includes the
variance, timeout, tool-call counts, and limitations behind those totals.

## Start here

For the shortest path, use the checked-in tasks and run the Harbor A/B. To learn
how the tasks were produced, use the Codex-guided Eval Author section. To test
only Insights, skip Harbor and NemoClaw entirely.

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo
make test
make validate
```

Follow the [single end-to-end walkthrough](docs/walkthrough.md). Supporting
references cover the [reusable harness patterns](docs/harness-patterns.md),
[measured results](docs/results.md), and the point at which this environment
should become a [NeMo Gym](docs/gym-extension.md).
