# Checked-in trace corpus

`world-v2/corpus/` contains 36 ATIF-v1.7 baseline traces: six trials for each
of six enterprise-assistant behavior families, collected across two clean
Hermes runs against `fixtures/world-v2.json`.

Relay ATOF was normalized to ATIF because the tested deployment did not emit
the session-close event needed for Relay's native snapshot. Every trace records
that transformation. Fixture-backed MCP calls retain their arguments and
results; unrelated local or web tool payloads use explicit redaction markers.
All people, systems, and records belong to the fictional Northstar world.

Validate the index, paths, IDs, schema, and six-per-family distribution:

```bash
python3 scripts/validate_trace_corpus.py traces/world-v2/corpus/index.json
```

To feed the pile to standalone Insights:

```bash
python3 scripts/convert_atif_for_insights.py \
  traces/world-v2/corpus --output .runs/insights/starting-corpus.jsonl
```

For a new corpus, collect Relay output through the optional NemoClaw path in
`docs/walkthrough.md`, then retain the same provenance and redaction review.
