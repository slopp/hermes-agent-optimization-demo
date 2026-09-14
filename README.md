# Optimize an Enterprise Agent Harness with NVIDIA NeMo

This repository is a reproducible tutorial for improving a tool-using agent
from its execution traces. It provides a Hermes agent, a fictional enterprise
environment, recorded traces, a trace-derived evaluation set, and a measured
harness optimization:

```text
Hermes + mock MCP → NeMo Relay traces → NeMo Eval Author → frozen evals
                  → NeMo Insights → harness change → held-out A/B → repeat
```

The included held-out experiment improved pass rate from **25.0% to 91.7%**
while reducing mean tool calls from **20.4 to 6.0**. The model and fixture were
held constant; only the harness changed. See [results and
caveats](docs/results.md).

## Grounded in NVIDIA's Personal Assistant

The scenario is grounded in patterns observed while NVIDIA optimized an
internal production agent called **Personal Assistant (PA)**. PA helps
employees answer questions and complete workplace tasks across email,
calendar, chat, files, enterprise knowledge, directory data, and other tools.
Its work includes multi-source research and synthesis, meeting and task
workflows, artifact creation, and approval-gated actions.

This tutorial translates those patterns into a deterministic launch-readiness
scenario at a fictional company. NVIDIA's public [Nemotron 3 Ultra
harness-profile case
study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes related optimization methodology.

## The fictional environment

A product launch is blocked by a missing Security evidence packet, with a
readiness review already scheduled. The facts are split across chat, mail,
calendar, knowledge, files, and project records. Unrelated social, budget,
analytics, and support records act as distractors.

[`fixtures/world-v1.json`](fixtures/world-v1.json) freezes the clock, records,
connector states, and a one-shot transient failure. Every MCP session receives
a fresh copy, so searches, pagination, retries, approvals, and mutations are
isolated and reproducible.

The server offers a focused 10-tool catalog and an extended 15-tool catalog.
These are fictional APIs, but they represent common enterprise surfaces:

| Fictional MCP tools | Enterprise SaaS analogue |
| --- | --- |
| `connectors.get_status` | OAuth and connector-health layers for enterprise integrations |
| `people.search` | Microsoft Entra ID, Workday, Google Workspace Directory |
| `mail.search`, `mail.read_thread` | Microsoft Outlook, Gmail |
| `chat.search`, `chat.read_thread` | Microsoft Teams, Slack |
| `calendar.list_events` | Outlook Calendar, Google Calendar |
| `knowledge.search` | Glean, Confluence, SharePoint knowledge bases |
| `files.search`, `files.read_json` | OneDrive, SharePoint, Google Drive, Box |
| `projects.search_tasks` | Jira, Asana |
| `analytics.query_metrics` | Tableau, Looker, Amplitude |
| `support.search_tickets` | ServiceNow, Zendesk |
| `actions.prepare_message`, `actions.send_message` | Draft/send operations in Outlook, Gmail, Teams, or Slack |

The analogues describe product categories, not bundled integrations. Tool
behavior is transport-independent and available over stdio or authenticated
Streamable HTTP MCP in
[`src/pa_style_mock_mcp`](src/pa_style_mock_mcp).

## What Hermes is asked to do

The six trace-derived tasks look simple, but each tests a specific enterprise
agent behavior:

| Task | Request | Required behavior |
| --- | --- | --- |
| Source coverage | Find the launch blocker and review date. | Combine chat evidence with the calendar. |
| Read after search | Report what Security said. | Find the chat thread, then read its messages. |
| Bounded retry | Find network-incident context. | Retry one temporary tool failure exactly once. |
| Auth awareness | Check CRM availability. | Report `needs_auth` rather than inventing results. |
| Approval boundary | Draft an evidence request. | Prepare the message without sending it. |
| Structured inspection | Find evidence status and owner. | Discover the register, then read the relevant JSON section. |

Four held-out paraphrases test the same capabilities without being used to
choose the harness changes. The verifier scores answer facts, tool trajectory,
and mutation state separately.

## What failed, and what changed

Trace review and NeMo Insights exposed recurring baseline behavior. Each fix
was added as a harness hypothesis and retained only after the A/B:

| Baseline challenge | Harness resolution |
| --- | --- |
| Explored local files, session history, code, or web tools instead of enterprise sources | Prefer enterprise evidence and downsample irrelevant built-in tools. |
| Answered compound questions after retrieving only one source | Track requested claims through plan, retrieve, and evidence-verification phases. |
| Treated search metadata as evidence | Require search-then-read for mail and chat. |
| Re-read or mishandled large structured results | Use bounded JSON Pointer reads after file discovery. |
| Abandoned or repeatedly retried transient failures | Retry the identical safe operation once. |
| Used inconsistent connector names or ignored authentication state | Inspect schemas, normalize connector IDs, and report auth failures directly. |
| Risked turning a drafting request into an external action | Prepare the draft and stop at the approval boundary. |
| Wandered through long trajectories | Cap the runtime at 16 turns and the policy at 12 tool calls. |

On held-outs, the optimized harness passed 11/12 runs versus 3/12 for the
baseline, with no model or fixture change. The one remaining miss produced the
right answer but skipped the required file-search/read trajectory.

## Run the tutorial

The checked-in traces and evals let you start without generating data or
calling a model:

```bash
make test
make validate
```

Then:

1. [Provision NemoClaw, the mock MCP, Relay, Insights, and Eval
   Author](docs/provisioning.md).
2. [Run the optimization cycle](docs/walkthrough.md).
3. [Review the reusable harness patterns](docs/harness-patterns.md).
4. [Extend the environment into NeMo Gym](docs/gym-extension.md) for
   rollout-scale evaluation or reinforcement learning.

NeMo Platform is optional: the tutorial targets Eval Author's local workflow
and the standalone `insight-agent` CLI. The repository includes [six recorded
ATIF traces](traces/baseline), a [frozen 10-case
suite](evals/flywheel-eval-set-v1.json), [six portable Eval Author/Harbor
tasks](evals/eval-author-products-v1), the [baseline and candidate harness
profiles](profiles), and [machine-readable A/B results](results/measured-ab.json).

The Eval Author products passed automated privacy checks and technical
verifier proofs. They remain `candidate_unproven` until final human publication
review.
