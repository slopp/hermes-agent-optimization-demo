# Optimize a Hermes enterprise-agent harness with NVIDIA NeMo

This runnable tutorial starts where many agent teams do: an agent and a collection
of production-like traces. It shows how to turn those traces into executable evals,
find recurring failures, change the agent harness, and measure whether the change
generalizes.

```text
remote mock MCP ← OpenShell-hosted Hermes + Relay traces → Codex + Eval Author
                              │                              │
                       network policy                  Harbor tasks
                              │                              │
                        baseline rollouts → Trace Analyst → candidate
                                                             │
                                              development A/B → held-out A/B
```

Everything needed for the fast path is checked in: 36 starting traces from the
OpenShell-hosted baseline, a deterministic 504-record fixture, ten trace-derived
Harbor tasks, a separately hosted Streamable HTTP MCP service, two Hermes profiles,
and measured reference results. You can reproduce the A/B without regenerating
either traces or evals; the walkthrough also shows how to replace each checked-in
input with your own. Eval Author proofs retain a task-local stdio adapter backed by
the exact same fixture and tool registry.

## Production grounding

The fictional agent is inspired by NVIDIA's work optimizing an internal production
assistant that helps employees research and act across email, calendars, chat,
files, enterprise knowledge, directories, and task systems. The tutorial distills
those problem shapes into synthetic data and deterministic tools. NVIDIA's public
[Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes the related optimization methodology.

The fictional world is a company preparing a product launch. It contains current
and stale projects, ambiguous people, paginated results, a large JSON evidence
register, a disconnected CRM connector, and one transient incident-search failure.

| Fictional MCP surface | Typical enterprise equivalent |
| --- | --- |
| people, mail, calendar | Workday or Entra ID; Outlook or Gmail; enterprise calendars |
| chat, knowledge, files | Teams or Slack; Confluence or Glean; SharePoint or Drive |
| projects, analytics, support | Jira or Asana; BI platforms; ServiceNow or Zendesk |
| connectors, actions | integration health; approval-gated draft and send APIs |

Codex and [NeMo Eval Author](https://github.com/NVIDIA-NeMo/nemo-platform/tree/9eb4fc7ca3e8dada9cfd66c72989ee735616c71f/plugins/nemo-eval-author/skills)
selected recurring behaviors from the starting traces and
encoded them as six development tasks. Four separately worded tasks were held back
until the candidate was frozen. Harbor runs Hermes against the fixture-backed MCP
server and scores the answer, actual tool calls, call budget, and mutation state.
Each model-backed trial runs in a short-lived [OpenShell](https://github.com/NVIDIA/OpenShell)
sandbox with default-deny network access and an endpoint-scoped NVIDIA credential;
the policy separately allows only the tutorial's authenticated MCP endpoint. Harbor
remains the task orchestrator and isolated verifier.

## What changed

The baseline uses a generic one-line policy, Hermes' broad built-in tool surface,
eager MCP exposure, and a 60-turn cap. Its evaluated rollouts showed incomplete
source coverage, searches cited without reading the selected record, loose retry
behavior, guessed structured-read arguments, and irrelevant local or web detours.

[NeMo Trace Analyst](https://github.com/NVIDIA-NeMo/labs-trace-intel) turns those
scored failures into hypotheses. A checked-in
[analysis](results/trace-analysis.yml) cites the failed traces, and the
[candidate proposal](results/candidate-proposal.md) separates its recurring
Trace Analyst finding from human review of the other verifier failures. The
candidate implements that proposal in an ordinary editable `SOUL.md`:
claim-to-source routing, an evidence-completeness check, search-then-read, schema-
first bounded JSON inspection, exact retry and fallback transitions, connector-
status awareness, prepare-without-send, tool downsampling, and a 12-turn cap.

| Trace Analyst evidence | Candidate response | Suite-level measurement |
| --- | --- | --- |
| Five failed cases skipped available enterprise tools and chose local/session paths, clarification, or unsupported answers | Route claims to authoritative sources; require search-then-read; downsample distracting tools behind discovery | Development: 0/6 → 3/6; held out: 1/4 → 2/4 |

| Split (saved OpenShell reference) | Baseline | Candidate | Attempts |
| --- | ---: | ---: | ---: |
| Development | 0/6 | 3/6 | one per task |
| Held out | 1/4 | 2/4 | one per task |

These are measured results on a small synthetic benchmark, not a claim that the
candidate policy is universal. See [results](docs/results.md) for runtime details and
limitations, and [harness patterns](docs/harness-patterns.md) for the portable
issue/fix ideas.

The complete saved evidence chain is machine checked:

`source traces → authored eval set → scored baseline → trace analysis → candidate proposal → candidate profile → measured A/B`

See [`results/artifact-chain.json`](results/artifact-chain.json), or run
`python3 scripts/validate_artifact_chain.py`. It verifies artifact hashes,
cross-references, exact harness controls, denominators, and candidate improvement.

## Start here

Use the [end-to-end walkthrough](docs/walkthrough.md). It offers a quick path using
the checked-in artifacts, a Trace-Analyst-only path, and an authoring path that uses
Codex with Eval Author. The [Gym extension](docs/gym-extension.md) explains when to
turn the same environment into a rollout or training environment.
