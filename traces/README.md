# Checked-in traces

`world-v2/corpus/` contains 36 Relay-compatible ATIF-v1.7 trajectories from
repeated baseline Hermes runs against the synthetic enterprise world. The index
records provenance and six observable behavior groups. Fixture-backed MCP calls
retain their schemas, arguments, and results; unrelated payloads use explicit
redaction markers.

These are the source traces used for Eval Author task design. They do not contain
Harbor scores:

```bash
python3 scripts/validate_trace_corpus.py traces/world-v2/corpus/index.json
```

`world-v2/baseline-eval/insights.jsonl` is a separate six-trace canonical JSONL
bundle from the measured baseline development run. Each record joins a Relay
trajectory with its Harbor reward and verifier findings in `evaluator_results`.
It lets the Insights-only path analyze real scored failures without rerunning the
agent. The bundle contains one trial for each development task: one passed and five
failed. The conversion unwraps Hermes' generic `tool_call` broker spans into the
actual MCP operation and retains schemas learned through `tool_search` and
`tool_describe`, so Trace Analyst sees capabilities that were dynamically exposed.

For a fresh Harbor job, produce the same contract with:

```bash
python3 scripts/convert_atif_for_insights.py \
  .runs/harbor/baseline-development \
  --output .runs/baseline-development-insights.jsonl
```

For your own agent, export Relay-compatible ATIF with stable IDs, task text, tool
calls/results, and reviewed provenance. The converter automatically joins Harbor
`result.json` and `verifier/report.json` files when they enclose each trajectory.
