# Codex prompt: derive Harbor evals from a trace pile

Work in this repository as an evaluation author. Read `ETHOS.md` first, then
read the complete `SKILL.md` files for these NeMo Eval Author skills from the
adjacent `../nemo-platform` checkout:

- `eval-author`
- `eval-author-audit`
- `eval-author-inspect-trace`
- `eval-author-trace-environment`
- `eval-author-task-create`

Inspect `traces/world-v2/corpus/index.json` and all 36 referenced ATIF traces.
Use the audit skill to define the finite behavior denominator and measure the
pile. Cluster repeated failure shapes and select one representative failed
trace for each meaningful development behavior. Explain the selections before
authoring tasks.

For every selected trace, follow the trace-environment skill end to end. The
task must exercise the task-local `enterprise-world` MCP server backed by
`fixtures/world-v2.json`; do not replace the source tools with a frozen query
shortcut. Record `real` tool access for those calls, prove MCP registration,
discovery, and invocation, and retain a separate no-network verifier. Run NOP,
Oracle, and negative controls. Do not claim a human review yourself: stop at
each privacy, tool-access, generalized-task, and publication review checkpoint,
show me the exact artifact to inspect, and wait for my decision.

Use this repository's existing `.harbor-venv/bin/python` and
`.harbor-venv/bin/harbor` for Harbor imports, checks, and proof jobs. Do not
silently install or upgrade Harbor while authoring the eval.

Treat `evals/harbor-tasks-v2/` as the checked-in reference implementation, not as
an answer to copy silently. Compare your proposed task contracts with it and
call out any substantive difference. Keep held-out cases sealed until the
development task and harness decisions are final.

Do not change application source or harness profiles during task authoring.
Write Eval Author working state only under `.eval-author/` unless I explicitly
approve exporting a reviewed artifact.
