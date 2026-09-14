# Promoting the mock environment to NeMo Gym

NeMo Gym is deliberately not required for the first flywheel in this example.
The checked-in traces, Eval Author products, standalone Insights analysis, and
matched harness A/B all run without it. Add Gym when the objective changes from
offline harness diagnosis to scalable rollout generation, interactive
benchmarking, or model/harness reinforcement learning.

This extension design follows NVIDIA's official
[Workplace Assistant resource server](https://github.com/NVIDIA-NeMo/Gym/tree/main/resources_servers/workplace_assistant)
at repository commit
[`1f47874`](https://github.com/NVIDIA-NeMo/Gym/commit/1f478743e3e9fa2e5b2819c11167e0641cda4ef9).
That implementation provides the relevant shape, but this demo does not depend
on or copy its environment. Gym APIs are evolving, so pin a tested Gym release
or commit before implementing the adapter.

## What carries over unchanged

| Existing demo component | Gym role | Fidelity requirement |
| --- | --- | --- |
| `fixtures/world-v1.json` | Frozen initial state for every sample | The fixture digest and clock must be recorded with every rollout. |
| `EnterpriseWorld` | Session-local mutable state | Construct a fresh deep copy in `seed_session`; never share approvals, outbox entries, or fault counters across samples. |
| `ToolRegistry.schemas()` | Tool definitions exposed by the resource server | Keep names, descriptions, argument schemas, result envelopes, pagination, and error codes identical to MCP. |
| `ToolRegistry.call()` | Resource-server tool dispatcher | Call the same transport-independent handler used by MCP; do not reimplement tool behavior. |
| `verify_case()` | Environment verifier | Preserve separate trajectory, answer, and state dimensions, plus the overall pass result. |
| `flywheel-eval-set-v1.json` | Evaluation task source | Preserve case IDs and partitions; translate the schema mechanically rather than rewriting prompts or expectations. |
| Relay/ATIF metadata | Rollout provenance | Retain arm, model returned by the provider, fixture/profile/catalog digests, case ID, trial, and session/call IDs. |

The official Workplace Assistant is useful implementation context because it
subclasses Gym's `SimpleResourcesServer`, registers tool schemas for MCP,
creates a tool environment in `seed_session`, dispatches calls through the
sample's session ID, verifies the completed response, and removes session state
after verification. Its verifier replays predicted and ground-truth mutations
into fresh worlds and compares resulting state. This demo needs the same
lifecycle but keeps its richer checks for evidence retrieval, final-answer
facts, approval boundaries, and efficiency.

## Minimal adapter shape

Create a separate adapter package; keep the existing MCP runtime as the public
starting experience:

```text
gym/
  pa_flywheel/
    app.py                  # SimpleResourcesServer adapter
    task_data.py            # Gym wire schema
    configs/pa_flywheel.yaml
    data/
      development.jsonl
      held_out.jsonl
```

The resource server should perform only lifecycle and wire-format work:

1. In `seed_session`, load the frozen fixture and create one `ToolRegistry` for
   the sample's Gym session ID.
2. In `mcp_tools`, translate each existing MCP `inputSchema` into Gym's tool
   schema envelope without changing semantics.
3. In the catch-all tool route, dispatch to that session's
   `ToolRegistry.call(name, arguments)` and return its existing result envelope.
4. In `verify`, reconstruct the call/result sequence and final text, run
   `verify_case`, return the scalar reward plus dimension diagnostics, and
   remove the session in a `finally` block.

Do not make the Gym adapter the source of truth. MCP and Gym should both import
the same world, registry, and verifier modules. That prevents a successful Gym
run from measuring an easier simulation than the one that produced the Hermes
traces.

## Task and reward contract

Gym's Workplace Assistant data places model input and tool schemas in
`responses_create_params`, with verifier fields alongside them. A mechanical
converter for this demo should emit, per case:

- the frozen user instruction and system clock;
- the exact focused or extended tool catalog and its digest;
- the existing `expectations` object;
- `case_id`, `case_kind`, partition, fixture digest, and harness arm;
- a maximum-step budget consistent with the measured NemoClaw run.

Use a strict primary reward: `1` only when trajectory, answer, and state all
pass; otherwise `0`. Return the individual dimensions as diagnostics and retain
tool-call count, retry count, and bytes read as guardrails. Do not train against
answer-string matching alone: it would reward unsupported synthesis and erase
the PA-style failure modes this example is meant to expose.

## Promotion gates

Before collecting training rollouts, run the same cases once through MCP and
once through Gym and require:

1. identical catalog and fixture digests;
2. identical tool outputs for a golden call sequence, including pagination,
   bounded JSON reads, auth failures, and the one-shot transient fault;
3. no state leakage across two concurrent sessions;
4. identical verifier dimensions for passing, incomplete, unsupported, and
   unauthorized-mutation controls;
5. the same held-out partition and no use of held-out results for tuning;
6. complete provenance sufficient to reproduce a rollout and attribute
   provider, harness, transport, or tool failures separately.

Only after these gates pass should `gym eval run` become an additional rollout
runner. The official Workplace Assistant demonstrates the command pattern:

```bash
gym env start --model-type openai_model --resources-server <pa-flywheel-resource>
gym eval run --no-serve \
  --agent <hermes-or-candidate-agent> \
  --input gym/pa_flywheel/data/development.jsonl \
  --output results/pa-flywheel-development-rollouts.jsonl
```

Treat those commands as an implementation target, not commands supported by
the current repository. When RL begins, train only on the development
partition, keep the frozen held-out A/B gate, and compare the trained policy
against both the original baseline and the winning harness-only candidate.
This separates gains from model learning, harness changes, and environment
drift.

## Where Data Designer fits

NeMo Gym's Workplace Assistant includes an optional Data Designer workflow for
generating multi-step tool-calling data. In this demo, use Data Designer only
to propose additional fictional fixture rows and task candidates. Validate and
freeze those rows before use. It must not synthesize the starting trace pile,
ground-truth judgments, held-out outcomes, or evidence that the tested agent
did not actually retrieve.
