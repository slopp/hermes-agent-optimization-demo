.PHONY: test validate validate-world-v1 validate-fixture streamable-http-check streamable-http-protocol-check mock-mcp-image mock-mcp-container-check insights-jsonl-atof insights-validate harbor-materialize nemoclaw-configure

test:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -v

validate:
	python3 scripts/generate_world_v2.py --check
	PYTHONPATH=src:. python3 scripts/validate_world_v2.py
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture fixtures/world-v2.json --cases evals/seed-suite-v2.json
	python3 scripts/validate_trace_corpus.py traces/world-v2/corpus/index.json
	python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v2.json
	python3 scripts/materialize_harbor_tasks.py --output .runs/reference-task-rebuild
	diff -qr evals/harbor-tasks-v2 .runs/reference-task-rebuild

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

harbor-materialize:
	python3 scripts/materialize_harbor_tasks.py --output .runs/reference-task-rebuild
	diff -qr evals/harbor-tasks-v2 .runs/reference-task-rebuild

nemoclaw-configure:
	@test -n "$(NEMOCLAW_GATEWAY)" || (echo "Set NEMOCLAW_GATEWAY=<gateway>" && exit 2)
	@test -n "$(NEMOCLAW_SANDBOX)" || (echo "Set NEMOCLAW_SANDBOX=<sandbox>" && exit 2)
	@test -n "$(ARM)" || (echo "Set ARM=baseline or candidate-v4" && exit 2)
	@test -n "$(TRACE_LABEL)" || (echo "Set TRACE_LABEL=<fresh-output-label>" && exit 2)
	python3 scripts/configure_nemoclaw_arm.py --gateway "$(NEMOCLAW_GATEWAY)" --sandbox "$(NEMOCLAW_SANDBOX)" --arm "$(ARM)" --trace-label "$(TRACE_LABEL)"
