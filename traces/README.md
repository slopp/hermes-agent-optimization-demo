# Checked-in trace bundle

`baseline/` contains six real Hermes traces collected in a NemoClaw-managed
OpenShell sandbox against `fixtures/world-v1.json`.

Relay 0.7.2 emitted complete ATOF turns but did not flush native ATIF because
Hermes 0.20.6 emitted no session-end event. The repository converted those
completed turns to ATIF-v1.7. Every trajectory records that structural loss.
For the public-data boundary, inputs and outputs from non-fixture tools were
replaced with explicit redaction markers; tool names and ordering remain so
the irrelevant-exploration pattern is still analyzable.

`manifest.json` hash-locks the fixture, six traces, and run provenance.
`eval-author-batch.json` is the tested local Eval Author input. Its six members
were promoted from prepared traces to technically proven Harbor candidates; the
exact declassified products are in `evals/eval-author-products-v1`.

The manifest remains `pending`. Automated scans found no credential literals,
host-user paths, or non-fictional identities, and Eval Author's agent contextual
privacy review completed for all six traces. A human must still review the exact
publication preview before this directory is released externally; after that,
set the manifest review to approved/complete and rerun:

```bash
python3 scripts/validate_trace_manifest.py traces/manifest.json
```

No Personal Assistant query, identity, transcript, or production tool payload
is included here.
