.PHONY: test validate validate-world-v1 validate-fixture streamable-http-check streamable-http-protocol-check mock-mcp-image mock-mcp-container-check insights-jsonl-atof insights-validate eval-author-prepare nemoclaw-configure score-traces

test:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -v

validate:
	python3 scripts/generate_world_v2.py --check
	PYTHONPATH=src:. python3 scripts/validate_world_v2.py
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture fixtures/world-v2.json --cases evals/seed-suite-v2.json
	python3 scripts/validate_trace_manifest.py traces/world-v2/manifest.json
	python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v2.json
	python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v2.json

validate-world-v1:
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture fixtures/world-v1.json --cases evals/seed-suite-v2.json

validate-fixture:
	@test -n "$(FIXTURE)" || (echo "Set FIXTURE=fixtures/world-vN.json" && exit 2)
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture "$(FIXTURE)" --skip-eval

streamable-http-check:
	PYTHONPATH=src uv run --with 'mcp==1.28.1' python scripts/check_streamable_http_adapter.py

streamable-http-protocol-check:
	PYTHONPATH=src uv run --with 'mcp==1.28.1' python scripts/check_streamable_http_protocol.py

mock-mcp-image:
	docker build -f deploy/mock-mcp/Dockerfile -t enterprise-world-mcp:local .

mock-mcp-container-check: mock-mcp-image
	uv run --with 'mcp==1.28.1' python scripts/check_mock_mcp_container.py --fixture /app/fixtures/world-v2.json --expected-text jordan.lee.security@example.test

insights-jsonl-atof:
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<Relay ATOF JSONL>" && exit 2)
	@test -n "$(INSIGHTS_OUTPUT)" || (echo "Set INSIGHTS_OUTPUT=<canonical.jsonl>" && exit 2)
	PYTHONPATH=src python3 scripts/convert_atof_for_insights.py --atof "$(INSIGHTS_INPUT)" --output "$(INSIGHTS_OUTPUT)" --matrix experiments/fidelity-matrix-v2.json

insights-validate:
	@test -n "$(INSIGHTS_CLI)" || (echo "Set INSIGHTS_CLI=/path/to/insight-agent" && exit 2)
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<canonical.jsonl>" && exit 2)
	$(INSIGHTS_CLI) validate --traces "$(INSIGHTS_INPUT)"
	$(INSIGHTS_CLI) coverage "$(INSIGHTS_INPUT)" --with-findings

eval-author-prepare:
	@test -n "$(EVAL_AUTHOR_PYTHON)" || (echo "Set EVAL_AUTHOR_PYTHON=<nemo-platform>/.venv/bin/python" && exit 2)
	@test -n "$(EVAL_AUTHOR_SCRIPT)" || (echo "Set EVAL_AUTHOR_SCRIPT=<trace_environment.py>" && exit 2)
	$(EVAL_AUTHOR_PYTHON) $(EVAL_AUTHOR_SCRIPT) batch-prepare --root .eval-author/world-v2-trace-environments --manifest traces/world-v2/eval-author-batch.json
	$(EVAL_AUTHOR_PYTHON) $(EVAL_AUTHOR_SCRIPT) batch-status --root .eval-author/world-v2-trace-environments --manifest traces/world-v2/eval-author-batch.json

nemoclaw-configure:
	@test -n "$(NEMOCLAW_GATEWAY)" || (echo "Set NEMOCLAW_GATEWAY=<gateway>" && exit 2)
	@test -n "$(NEMOCLAW_SANDBOX)" || (echo "Set NEMOCLAW_SANDBOX=<sandbox>" && exit 2)
	@test -n "$(ARM)" || (echo "Set ARM=baseline, candidate-v3, or candidate-v4" && exit 2)
	@test -n "$(TRACE_LABEL)" || (echo "Set TRACE_LABEL=<fresh-output-label>" && exit 2)
	python3 scripts/configure_nemoclaw_arm.py --gateway "$(NEMOCLAW_GATEWAY)" --sandbox "$(NEMOCLAW_SANDBOX)" --arm "$(ARM)" --trace-label "$(TRACE_LABEL)"

score-traces:
	@test -n "$(BASELINE_TRACES)" || (echo "Set BASELINE_TRACES=<canonical.jsonl>" && exit 2)
	@test -n "$(CANDIDATE_TRACES)" || (echo "Set CANDIDATE_TRACES=<canonical.jsonl>" && exit 2)
	python3 scripts/score_insights_traces.py --valid-only --suite evals/flywheel-eval-set-v2.json --arm baseline="$(BASELINE_TRACES)" --arm candidate-v4="$(CANDIDATE_TRACES)" --output .runs/world-v2/ab-report.json
