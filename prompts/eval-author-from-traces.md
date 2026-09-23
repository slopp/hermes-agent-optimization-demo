# Codex prompt: propose Harbor evals from observed traces

Use the installed `eval-author` skills to help me design evaluations for this
agent. Read `ETHOS.md` and the complete instructions for every Eval Author skill
you invoke before taking action.

Our starting evidence is `traces/world-v2/corpus/index.json` and every ATIF file
it references. Inspect the entire indexed corpus. Do not assume how many behaviors
or tasks it should produce. Report:

1. the finite trace denominator you inspected;
2. the recurring behaviors and gaps supported by trace IDs;
3. your selection criteria and representative trace choices; and
4. behaviors you excluded or deferred, with reasons.

After I approve the plan, apply the trace-derived environment workflow separately
to each selected trace. Preserve the behavior under test while generalizing
identities and data. The task must exercise the task-local `enterprise-world` MCP
server backed by `fixtures/world-v2.json`; do not substitute a frozen answer lookup.
Classify those calls according to the skill's access taxonomy and prove MCP
registration, discovery, and invocation.

Use this repository's existing `.harbor-venv/bin/python` and
`.harbor-venv/bin/harbor` for checks and proof jobs. Do not install or upgrade
Harbor. Require NOP failure, Oracle success, relevant negative controls, and a
separate no-network verifier.

Stop at every required human privacy, tool-access, task-meaning, and publication
review. Show the exact artifact and decision being reviewed; do not attest on my
behalf or change a review field to bypass a gate.

Keep working state under `.eval-author/`. Do not inspect
`evals/harbor-tasks-v2/` until after you have presented an independently derived
task plan. Once approved, compare your proposed contracts with that reference set
and explain substantive differences. Do not modify application code, harness
profiles, or held-out tasks while authoring development evals.
