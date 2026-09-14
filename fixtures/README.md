# Fixture lifecycle

`world-v1.json` is the frozen, reviewed runtime input. Do not regenerate it as
part of a trace or evaluation run.

When more variety is useful, use NeMo Data Designer to expand the structural
constraints in `generation/world-blueprint-v1.json` into fictional records.
Then apply this promotion process:

1. Export only structured candidate records; never ask Data Designer to emit an
   agent trajectory, tool call, ATOF, or ATIF record.
2. Adapt the generated records to the `world-v1.json` contract.
3. Run the candidate-fixture check and review every string for the public-data
   boundary. The existing seed eval cases are intentionally tied to v1, so do
   not use them to claim a generated v2 fixture is evaluation-compatible:

   ```bash
   make validate-fixture FIXTURE=fixtures/world-v2.json
   ```

   Then add/validate a matching fixture-specific eval contract before any
   collection.
4. Create a new versioned fixture (`world-v2.json`), pin its SHA-256 in the
   resulting trace manifest, and collect fresh real Hermes traces.

For structured exports, generate only JSON records matching the
`structured_files` contract. Their discovery metadata must remain distinct from
their `content`: the runtime exposes the latter only through the bounded
`files.read_json` JSON Pointer tool. This lets the fidelity matrix test a
realistic search → opaque-ID → inspection workflow without using generated
traces.

This separation prevents two common errors: using synthetic trajectories as
observability evidence, and allowing generated fixture changes to silently
invalidate an existing regression suite.
