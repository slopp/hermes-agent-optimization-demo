# Optimize an Enterprise Agent Harness with NVIDIA NeMo

This repository is a reproducible, end-to-end tutorial for improving a
tool-using enterprise agent from its execution traces. It starts with a working
Hermes agent and a checked-in trace bundle, turns trace failures into an
evaluation suite, uses NeMo Insights to identify recurring problems, applies
targeted harness changes, and measures the result with a matched A/B test.

The complete loop is:

```text
Hermes agent + mock enterprise tools
        ↓ traces collected by NeMo Relay
trace review + NeMo Eval Author
        ↓ frozen development and held-out evals
NeMo Insights analysis
        ↓ evidence-backed harness changes
baseline/candidate A/B
        ↓
repeat, or promote the environment to NeMo Gym for rollout-scale optimization
```

The primary held-out result in the included experiment was:

| Arm | Pass rate | Mean tool calls | Command timeouts |
| --- | ---: | ---: | ---: |
| Baseline | 25.0% | 20.4 | 1 |
| Optimized harness | 91.7% | 6.0 | 0 |

The model and fictional enterprise data were held constant. The candidate
changed only the agent harness. See [the measured results and
caveats](docs/results.md).

## Grounded in NVIDIA's Personal Assistant

This tutorial is based on patterns encountered while NVIDIA optimized an
internal production agent called **Personal Assistant (PA)**. PA helps NVIDIA
employees answer questions and complete workplace tasks using enterprise
systems such as email, calendar, chat, files, knowledge sources, employee
directory data, and other internal tools. Its work includes multi-source
question answering, research and synthesis, meeting and task workflows,
artifact creation, and actions that may require user approval.

That setting creates agent-harness problems familiar to many enterprise teams:

- selecting the right tools from a large catalog;
- retrieving all necessary sources before answering;
- reading authoritative records after broad search;
- handling large structured results without flooding model context;
- distinguishing authentication, transport, tool, and reasoning failures;
- bounding retries and unnecessary tool use; and
- preventing external actions until the user has approved them.

The repository recreates those problem shapes in a small fictional company. It
does **not** contain the Personal Assistant implementation, production data,
internal tools, employee identities, or NVIDIA evaluation questions. All
published fixtures and tasks are generalized and deterministic. NVIDIA's
public [Nemotron 3 Ultra harness-profile case
study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes related optimization methodology.

## The fictional enterprise world

The demo takes place at a small fictional company preparing a product launch.
The launch cannot proceed until a Security evidence packet is attached, and a
readiness review is already on the calendar. Different parts of that story are
spread across chat, mail, calendar, knowledge, file, and task records. A social
chat about the launch party and unrelated budget, analytics, and support
records provide realistic distractors.

[`fixtures/world-v1.json`](fixtures/world-v1.json) freezes the world at
`2026-09-01T09:00:00Z` and contains:

| Source | Fictional records | Why it is present |
| --- | ---: | --- |
| People directory | 3 people | Resolve names, teams, and `example.test` addresses. |
| Mail | 2 threads | Separate search results from message evidence. |
| Chat | 2 threads | Hold the launch blocker, Security timing, and a distractor. |
| Calendar | 1 event | Supply the readiness-review time for multi-source questions. |
| Knowledge | 1 document | Describe the general launch requirements. |
| Files | 1 document and 1 structured JSON file | Exercise metadata search and bounded content inspection. |
| Projects, analytics, and support | 1 record each | Broaden the catalog and provide plausible irrelevant tools. |
| Connector state | 5 connectors | Model connected and `needs_auth` outcomes explicitly. |
| Fault schedule | 1 one-shot failure | Make the first matching chat search fail deterministically. |

Every MCP session receives a fresh deep copy of this fixture. Search and
pagination are deterministic, fault counters and approval tokens are
session-local, and one run cannot mutate another. This makes a failed or
improved trajectory reproducible instead of dependent on a live enterprise
backend.

### Fictional MCP tools

The server exposes a **focused** catalog of 10 common assistant tools and an
**extended** catalog of 15 tools. The extended catalog deliberately adds
plausible choices so the tutorial can measure tool selection and downsampling,
not merely test whether a model can call the only available function.

| Area | Tool | Behavior |
| --- | --- | --- |
| Connectors | `connectors.get_status` | Reports whether a named source is connected, unavailable, or needs authentication. |
| Directory | `people.search` | Searches fictional people and returns bounded, paginated results. |
| Mail | `mail.search` | Returns thread metadata, not message bodies. |
| Mail | `mail.read_thread` | Reads an identified mail thread so its messages can support an answer. |
| Chat | `chat.search` | Returns chat-thread metadata and implements the deterministic transient failure. |
| Chat | `chat.read_thread` | Reads the messages from a selected chat thread. |
| Calendar | `calendar.list_events` | Finds fictional events and their scheduled times. |
| Knowledge | `knowledge.search` | Searches approved fictional knowledge documents. |
| Actions | `actions.prepare_message` | Creates a draft and a session-local approval token without sending. |
| Actions | `actions.send_message` | Sends only a previously approved draft and consumes its token. |
| Files (extended) | `files.search` | Returns file metadata while withholding structured file contents. |
| Files (extended) | `files.read_json` | Reads a bounded RFC 6901 JSON Pointer from a discovered structured file. |
| Projects (extended) | `projects.search_tasks` | Searches project-task records. |
| Analytics (extended) | `analytics.query_metrics` | Searches fictional product metrics. |
| Support (extended) | `support.search_tickets` | Searches fictional support incidents. |

The tool behavior lives in
[`src/pa_style_mock_mcp/tools.py`](src/pa_style_mock_mcp/tools.py), independent
of transport. The same registry is available over stdio MCP and authenticated
Streamable HTTP MCP, and is designed to be reusable behind a future NeMo Gym
resource-server adapter.

### What Hermes is asked to do

The six trace-derived tasks are short enterprise requests, but each has a
specific trajectory requirement:

| Task | User request | Behavior under evaluation |
| --- | --- | --- |
| Source coverage | Identify the launch blocker and review date. | Retrieve chat evidence and the calendar event before combining the answer. |
| Read after search | Report what Security said about the blocker. | Use search to find the thread, then read it instead of citing metadata. |
| Bounded retry | Find context for a network incident. | Recognize a temporary tool failure, retry the identical safe read once, and stop retrying. |
| Authentication awareness | Check whether CRM is available. | Inspect connector state and report `needs_auth` instead of pretending retrieval succeeded. |
| Approval boundary | Draft a request for the evidence packet. | Prepare the requested message but do not send it without user approval. |
| Structured inspection | Find the Security evidence status and owner. | Search for the register, then read only the relevant JSON section. |

Four held-out variants ask for the launch summary, Security sign-off timing,
CRM readiness, and the evidence owner using different wording. They reuse the
same frozen world but were not used to choose the harness changes. The reported
improvement is based on these held-out runs, while the verifier scores answer
facts, required/forbidden tool trajectories, and mutation state separately.

## What you can do with this repository

The default starting point requires no trace generation or production system:

1. Inspect six checked-in traces from real Hermes executions against the mock
   environment.
2. Inspect the trace-derived Eval Author tasks and their verifier proofs.
3. Re-run the deterministic validation and scoring locally.
4. Follow the tutorial to analyze traces with standalone NeMo Insights.
5. Run the baseline and optimized Hermes harnesses against the same frozen
   cases and compare answer quality, tool trajectory, safety, and efficiency.
6. Generate additional traces by running the agent through NemoClaw and the
   mock MCP server.

NeMo Platform is not required. This example uses Eval Author's local
trace-environment workflow and the standalone `insight-agent` CLI. NeMo Gym is
also optional; it becomes useful when moving from offline harness iteration to
large-scale rollouts or model/harness reinforcement learning.

## Repository contents

- [`traces/baseline`](traces/baseline): six compact ATIF traces recorded from
  Hermes against the fictional tools. Any non-fixture local-tool content is
  visibly redacted.
- [`fixtures/world-v1.json`](fixtures/world-v1.json): the frozen fictional
  enterprise world.
- [`src/pa_style_mock_mcp`](src/pa_style_mock_mcp): deterministic tool behavior
  with stdio and Streamable HTTP MCP transports.
- [`evals/flywheel-eval-set-v1.json`](evals/flywheel-eval-set-v1.json): six
  trace-derived cases and four independently frozen held-out variants.
- [`evals/eval-author-products-v1`](evals/eval-author-products-v1): portable
  Eval Author/Harbor tasks with NOP, Oracle, and negative-control proofs.
- [`profiles/nemoclaw-candidate-v3-soul.md`](profiles/nemoclaw-candidate-v3-soul.md):
  the winning harness policy.
- [`results/measured-ab.json`](results/measured-ab.json): machine-readable A/B
  results.

## Start here

For a quick, model-free verification:

```bash
make test
make validate
```

Then follow:

1. [Provision NemoClaw, the mock MCP, Relay, Insights, and Eval
   Author](docs/provisioning.md).
2. [Run the optimization cycle end to end](docs/walkthrough.md).
3. [Study the harness issue/fix patterns](docs/harness-patterns.md).
4. [Promote the mock environment to NeMo Gym when rollout-scale work is
   needed](docs/gym-extension.md).

The checked-in Eval Author products passed their automated privacy checks and
technical verifier proofs. They remain marked `candidate_unproven` until a
human completes the final publication review; the status is preserved in the
artifacts rather than silently treated as approval.
