# Eval Author products for world-v2

These six directories are exact exports from NeMo Eval Author's local
trace-environment workflow. Each task was run as five isolated Harbor 0.22.0
jobs: two NOPs scored `0`, two Oracles scored `1`, and one incomplete-answer
control scored `0`.

The verifier ran separately with networking disabled. An agent reviewed the
exact export bytes; the products remain explicitly unproven until a human
reviews the generalized tasks and their Relevant experience sections.

```bash
python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v2.json
```
