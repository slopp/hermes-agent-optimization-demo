# When to extend the demo into NeMo Gym

Gym is not required for the trace-to-harness cycle. Add it when you need
rollout-scale evaluation, an interactive benchmark, or model/harness
reinforcement learning.

NVIDIA's
[Workplace Assistant resource server](https://github.com/NVIDIA-NeMo/Gym/tree/main/resources_servers/workplace_assistant)
is the closest reference architecture: seed isolated session state, expose MCP
schemas, dispatch calls by session, verify the completed trajectory, and clean
up state. Pin a tested Gym revision because its APIs evolve.

## Reuse the same source of truth

| Existing component | Gym role |
| --- | --- |
| `fixtures/world-v2.json` | fresh initial state for each sample |
| `EnterpriseWorld` | session-local mutable state |
| `ToolRegistry.schemas()` | resource-server tool definitions |
| `ToolRegistry.call()` | shared dispatcher |
| `verify_case()` | answer, trajectory, and state reward dimensions |
| `flywheel-eval-set-v2.json` | development and held-out task source |

The Gym adapter should contain only lifecycle and wire-format code. MCP and Gym
must import the same world, registry, and verifier so training cannot target an
easier simulation.

Use a strict primary reward of 1 only when answer, trajectory, and state all
pass. Retain tool calls, retries, bytes read, and timeouts as diagnostics.

## Parity gates

Before generating training rollouts, require:

1. identical fixture and tool-catalog digests;
2. identical results for pagination, JSON Pointer reads, auth errors, transient
   retry, and approval flows;
3. no state leakage across concurrent sessions;
4. identical verifier outcomes for passing, incomplete, unsupported, and
   unauthorized-mutation controls; and
5. the same frozen held-out partition and provenance fields.

Only then add `gym eval run`. Train on development cases and retain the
Harbor held-out A/B as the external gate so model-learning gains remain
separable from harness changes and environment drift.

Data Designer may propose additional fictional fixture rows and task
candidates. Review and freeze them before use; it should not fabricate the
starting trace corpus or verifier judgments.
