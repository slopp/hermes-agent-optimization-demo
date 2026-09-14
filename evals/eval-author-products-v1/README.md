# Eval Author trace-derived products v1

The six sibling directories are exact exports from NeMo Eval Author's local
trace-environment workflow. Each contains a generalized Harbor task, candidate
record, reproducibility manifest, and declassified result.

Every task was executed as five independent Harbor 0.22.0 jobs:

- two NOP runs, both reward `0`;
- two Oracle runs, both reward `1`; and
- one task-specific incomplete-answer negative control, reward `0`.

All jobs completed without exceptions using separate, no-network verifiers.
The exports intentionally report `environment.status = "unproven"` and
`review_status = "unreviewed"`: an agent reviewed the exact publication bytes,
but a human has not yet approved the generalized tasks or Relevant experience.
Do not relabel these products as publication-ready without completing that gate.

Validate the checked-in proof records with:

```bash
python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v1.json
```
