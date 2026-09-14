# Checked-in trace bundle

`world-v2/baseline/` contains one Hermes baseline trace for each of the six
development tasks. They were collected in a NemoClaw-managed OpenShell sandbox
against `fixtures/world-v2.json`.

Relay emitted complete ATOF turn scopes. The checked-in ATIF-v1.7 files were
normalized from those scopes because the tested integration did not emit the
session-end event required for Relay's native ATIF snapshot. Each trajectory
records that loss, and non-fixture tool payloads were replaced with explicit
redaction markers.

`world-v2/manifest.json` hash-locks the fixture, traces, and provenance.
`world-v2/eval-author-batch.json` is the matching Eval Author input.

```bash
python3 scripts/validate_trace_manifest.py traces/world-v2/manifest.json
```

Automated and contextual reviews found only fictional fixture content and
explicit redactions. The manifest remains pending until a human completes the
publication review.

For a future Relay version that emits native ATIF at session close, use
`scripts/convert_atif_for_insights.py` directly instead of normalizing ATOF.
For this bundle's filenames, pass `--case-id-from-stem`.
