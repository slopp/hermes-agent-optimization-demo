# Optimize a Hermes agent harness with NVIDIA NeMo

This repository is a reproducible tutorial for improving a tool-using
enterprise agent from its traces:

```text
Hermes in NemoClaw + mock MCP → Relay traces → Eval Author → frozen eval
                                  ↓
                           NeMo Insights
                                  ↓
                     harness change → held-out A/B
```

You can begin with the checked-in traces and eval products, so generating data
is optional. The complete workflow uses standalone NeMo Insights and Eval
Author locally; a NeMo Platform deployment is not required. The standalone
Insight Agent source is currently an access-controlled NVIDIA preview, while
the checked-in traces, eval products, mock environment, and remaining workflow
can be inspected without it.

## Production grounding

The problem shapes come from NVIDIA's optimization of Personal Assistant, an
internal production agent that helps employees research and act across email,
calendar, chat, files, enterprise knowledge, directories, and task systems.
Typical work includes multi-source synthesis, meeting and task workflows,
artifact creation, and approval-gated actions.

The tutorial moves those shapes into Northstar, a fictional company preparing
a product launch. Its deterministic 504-record world includes ambiguous people,
stale and unrelated records, paginated search, a large JSON evidence register,
a disconnected CRM, and one transient incident-search failure. NVIDIA's public
[Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes the related methodology.

## Fictional tools and tasks

| MCP surface | Enterprise analogue |
| --- | --- |
| people, mail, calendar | Entra ID/Workday, Outlook/Gmail, enterprise calendars |
| chat, knowledge, files | Teams/Slack, Confluence/Glean, SharePoint/Drive |
| projects, analytics, support | Jira/Asana, BI platforms, ServiceNow/Zendesk |
| connectors, actions | integration health and approval-gated draft/send APIs |

The six trace-derived tasks test multi-source coverage, search-then-read,
bounded retry, connector authentication, prepare-without-send, and bounded JSON
inspection. Four held-out paraphrases test whether the harness changes
generalize.

The broad baseline often explored local, web, code, or session tools; stopped
after one source; guessed tool arguments; enumerated records; or retried
loosely. Insights motivated a narrower evidence-state harness with
claim-to-source routing, schema-first calls, search-then-read, exact one-shot
retry, JSON Pointer reads, approval boundaries, irrelevant-tool downsampling,
and explicit call/turn budgets.

With the same world and returned model, held-out pass rate improved from
**50.0% (6/12) to 100% (12/12)** while mean tool calls fell from **12.75 to
4.33**. Development improved from **22.2% to 94.4%**. See
[results and caveats](docs/results.md).

## Start here

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo
make test
make validate
```

Then follow the single [end-to-end walkthrough](docs/walkthrough.md). It covers
NemoClaw/Hermes and mock-MCP setup, optional trace recollection, Relay
conversion, Eval Author, Insights, both harness arms, and the held-out A/B.

Useful supporting references:

- [Reusable harness patterns](docs/harness-patterns.md)
- [Measured result](docs/results.md)
- [When and how to extend this environment into NeMo Gym](docs/gym-extension.md)
- [Fixture](fixtures/README.md) and [trace bundle](traces/README.md) provenance

`world-v2.json` is the tutorial fixture. The smaller `world-v1.json` remains
only as a fast unit-test and fixture-generation seed.
