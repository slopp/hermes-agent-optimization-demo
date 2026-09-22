.PHONY: test validate validate-world-v1 validate-fixture insights-jsonl-atof harbor-materialize

test:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -v

validate:
	python3 scripts/generate_world_v2.py --check
	PYTHONPATH=src:. python3 scripts/validate_world_v2.py
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture fixtures/world-v2.json --cases evals/seed-suite-v2.json
	python3 scripts/validate_trace_corpus.py traces/world-v2/corpus/index.json
	python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v2.json
	python3 scripts/materialize_harbor_tasks.py --output .runs/reference-task-rebuild
	diff -qr -x __pycache__ -x '*.pyc' evals/harbor-tasks-v2 .runs/reference-task-rebuild

validate-world-v1:
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture fixtures/world-v1.json --cases evals/seed-suite-v2.json

validate-fixture:
	@test -n "$(FIXTURE)" || (echo "Set FIXTURE=fixtures/world-vN.json" && exit 2)
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture "$(FIXTURE)" --skip-eval

insights-jsonl-atof:
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<Relay ATOF JSONL>" && exit 2)
	@test -n "$(INSIGHTS_OUTPUT)" || (echo "Set INSIGHTS_OUTPUT=<canonical.jsonl>" && exit 2)
	PYTHONPATH=src python3 scripts/convert_atof_for_insights.py --atof "$(INSIGHTS_INPUT)" --output "$(INSIGHTS_OUTPUT)" --matrix experiments/fidelity-matrix-v2.json

harbor-materialize:
	python3 scripts/materialize_harbor_tasks.py --output .runs/reference-task-rebuild
	diff -qr -x __pycache__ -x '*.pyc' evals/harbor-tasks-v2 .runs/reference-task-rebuild
