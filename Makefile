.PHONY: test validate validate-fixture mcp-sdk-check streamable-http-check streamable-http-protocol-check mock-mcp-image mock-mcp-container-check hermes-mcp-check hermes-profile-check inference-hub-check provision-check stage-platform-profile validate-platform-profile validate-candidate-experiment fidelity-collect fidelity-coverage summarize-collection prepare-collection-review insights-jsonl insights-jsonl-atof insights-validate eval-author-prepare nemoclaw-configure score-traces validate-trace-manifest validate-intake-bindings validate-trace-derived-suite validate-eval-author-products

test:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -v

validate:
	PYTHONPATH=src python3 scripts/validate_contract.py
	python3 scripts/validate_trace_manifest.py traces/manifest.json
	python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v1.json
	python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v1.json

# Validates a prospective Data Designer fixture without applying the v1 eval cases.
validate-fixture:
	@test -n "$(FIXTURE)" || (echo "Set FIXTURE=fixtures/world-vN.json" && exit 2)
	PYTHONPATH=src python3 scripts/validate_contract.py --fixture "$(FIXTURE)" --skip-eval

mcp-sdk-check:
	uv run --with 'mcp>=1.0,<2.0' python scripts/check_mcp_sdk.py

streamable-http-check:
	PYTHONPATH=src uv run --with 'mcp==1.28.1' python scripts/check_streamable_http_adapter.py

streamable-http-protocol-check:
	PYTHONPATH=src uv run --with 'mcp==1.28.1' python scripts/check_streamable_http_protocol.py

# Builds only a local image; it does not run, publish, or register a service.
mock-mcp-image:
	docker build -f deploy/mock-mcp/Dockerfile -t pa-style-mock-mcp:local .

# Builds then runs a short-lived loopback container with a fixture-only token.
mock-mcp-container-check: mock-mcp-image
	uv run --with 'mcp==1.28.1' python scripts/check_mock_mcp_container.py

# Override HERMES_SOURCE if the Hermes checkout lives elsewhere.
HERMES_SOURCE ?= $(CURDIR)/../../hermes-agent

hermes-mcp-check:
	PYTHONPATH=$(HERMES_SOURCE):src uv run --with 'mcp==1.28.1' --with 'pyyaml==6.0.3' python scripts/check_hermes_mcp_discovery.py

hermes-profile-check:
	cd $(HERMES_SOURCE) && PYTHONPATH=$(CURDIR):$(CURDIR)/src uv run --extra mcp python $(CURDIR)/scripts/check_hermes_profile.py

inference-hub-check:
	python3 scripts/check_inference_hub.py

# Local-only, credential-safe prerequisite report. Use PROVISION_ARGS='--target local', etc.
provision-check:
	python3 scripts/check_provisioning.py --hermes-source "$(HERMES_SOURCE)" $(PROVISION_ARGS)

# Writes an agent-local optimizer.yaml and AGENT-SPEC.md; it never contacts Platform.
stage-platform-profile:
	@test -n "$(PLATFORM_WORKSPACE)" || (echo "Set PLATFORM_WORKSPACE=<approved-workspace>" && exit 2)
	@test -n "$(PLATFORM_PROFILE_DIR)" || (echo "Set PLATFORM_PROFILE_DIR=<agent-local-directory>" && exit 2)
	python3 scripts/stage_platform_profile.py --output-dir "$(PLATFORM_PROFILE_DIR)" --workspace "$(PLATFORM_WORKSPACE)" $(PLATFORM_PROFILE_ARGS)

validate-platform-profile:
	@test -n "$(PLATFORM_PROFILE_DIR)" || (echo "Set PLATFORM_PROFILE_DIR=<agent-local-directory>" && exit 2)
	python3 scripts/validate_platform_profile.py "$(PLATFORM_PROFILE_DIR)" $(PLATFORM_PROFILE_VALIDATE_ARGS)

# Requires locally exported HERMES_SOURCE and NVIDIA_API_KEY. Override MATRIX_ARGS for a subset/dry run.
fidelity-collect:
	python3 scripts/run_fidelity_matrix.py $(MATRIX_ARGS)

# Run after fidelity-collect; checks observed tool coverage but does not diagnose failures.
fidelity-coverage:
	python3 scripts/check_fidelity_coverage.py $(COVERAGE_ARGS)

summarize-collection:
	@test -n "$(RUN_ROOT)" || (echo "Set RUN_ROOT=.runs/<route>/<arm>/<collection-id>" && exit 2)
	python3 scripts/summarize_collection.py --run-root "$(RUN_ROOT)" $(SUMMARY_ARGS)

# Writes only hashes, counts, and tool-name coverage; it never promotes or uploads traces.
prepare-collection-review:
	@test -n "$(RUN_ROOT)" || (echo "Set RUN_ROOT=.runs/<route>/<arm>/<collection-id>" && exit 2)
	@test -n "$(REVIEW_TRIALS)" || (echo "Set REVIEW_TRIALS=<known-trials-per-scenario>" && exit 2)
	@test -n "$(REVIEW_OUTPUT)" || (echo "Set REVIEW_OUTPUT=/tmp/collection-review-dossier.json" && exit 2)
	python3 scripts/prepare_collection_review.py --run-root "$(RUN_ROOT)" --trials "$(REVIEW_TRIALS)" --output "$(REVIEW_OUTPUT)" $(REVIEW_ARGS)

# Convert real Relay ATIF output to the canonical filesystem contract consumed
# by the standalone insight-agent CLI. INSIGHTS_INPUT may be a file or directory.
insights-jsonl:
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<ATIF file-or-directory>" && exit 2)
	@test -n "$(INSIGHTS_OUTPUT)" || (echo "Set INSIGHTS_OUTPUT=<canonical.jsonl>" && exit 2)
	PYTHONPATH=src python3 scripts/convert_atif_for_insights.py "$(INSIGHTS_INPUT)" --output "$(INSIGHTS_OUTPUT)" --case-id-from-parent

insights-jsonl-atof:
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<Relay ATOF JSONL>" && exit 2)
	@test -n "$(INSIGHTS_OUTPUT)" || (echo "Set INSIGHTS_OUTPUT=<canonical.jsonl>" && exit 2)
	PYTHONPATH=src python3 scripts/convert_atof_for_insights.py --atof "$(INSIGHTS_INPUT)" --output "$(INSIGHTS_OUTPUT)" --matrix experiments/fidelity-matrix.json

# Standalone Insights is the default analysis target; set INSIGHTS_CLI to its executable.
insights-validate:
	@test -n "$(INSIGHTS_CLI)" || (echo "Set INSIGHTS_CLI=/path/to/insight-agent" && exit 2)
	@test -n "$(INSIGHTS_INPUT)" || (echo "Set INSIGHTS_INPUT=<canonical.jsonl>" && exit 2)
	$(INSIGHTS_CLI) validate --traces "$(INSIGHTS_INPUT)"
	$(INSIGHTS_CLI) coverage "$(INSIGHTS_INPUT)" --with-findings

# Eval Author source checkout only; no NeMo Platform service is required.
eval-author-prepare:
	@test -n "$(EVAL_AUTHOR_PYTHON)" || (echo "Set EVAL_AUTHOR_PYTHON=<nemo-platform>/.venv/bin/python" && exit 2)
	@test -n "$(EVAL_AUTHOR_SCRIPT)" || (echo "Set EVAL_AUTHOR_SCRIPT=<trace_environment.py>" && exit 2)
	$(EVAL_AUTHOR_PYTHON) $(EVAL_AUTHOR_SCRIPT) batch-prepare --root .eval-author/public-trace-environments --manifest traces/eval-author-batch.json
	$(EVAL_AUTHOR_PYTHON) $(EVAL_AUTHOR_SCRIPT) batch-status --root .eval-author/public-trace-environments --manifest traces/eval-author-batch.json

nemoclaw-configure:
	@test -n "$(NEMOCLAW_GATEWAY)" || (echo "Set NEMOCLAW_GATEWAY=<gateway>" && exit 2)
	@test -n "$(NEMOCLAW_SANDBOX)" || (echo "Set NEMOCLAW_SANDBOX=<sandbox>" && exit 2)
	@test -n "$(ARM)" || (echo "Set ARM=baseline or candidate-v3" && exit 2)
	@test -n "$(TRACE_LABEL)" || (echo "Set TRACE_LABEL=<fresh-output-label>" && exit 2)
	python3 scripts/configure_nemoclaw_arm.py --gateway "$(NEMOCLAW_GATEWAY)" --sandbox "$(NEMOCLAW_SANDBOX)" --arm "$(ARM)" --trace-label "$(TRACE_LABEL)"

score-traces:
	@test -n "$(BASELINE_TRACES)" || (echo "Set BASELINE_TRACES=<canonical.jsonl>" && exit 2)
	@test -n "$(CANDIDATE_TRACES)" || (echo "Set CANDIDATE_TRACES=<canonical.jsonl>" && exit 2)
	python3 scripts/score_insights_traces.py --valid-only --suite evals/flywheel-eval-set-v1.json --arm baseline="$(BASELINE_TRACES)" --arm candidate-v3="$(CANDIDATE_TRACES)" --output "$${OUTPUT:-.runs/ab-report.json}"

# Requires a reviewed traces/manifest.json created by promote_reviewed_trace.py.
validate-trace-manifest:
	python3 scripts/validate_trace_manifest.py $(TRACE_MANIFEST)

# Optional Platform path: validates reviewed Intake bindings when an organization uses Intake.
validate-intake-bindings:
	@test -n "$(INTAKE_BINDINGS)" || (echo "Set INTAKE_BINDINGS=traces/intake-bindings.json" && exit 2)
	python3 scripts/validate_intake_bindings.py $(INTAKE_BINDINGS) $(TRACE_MANIFEST)

validate-trace-derived-suite:
	@test -n "$(SUITE)" || (echo "Set SUITE=path/to/approved-suite.json" && exit 2)
	python3 scripts/validate_trace_derived_suite.py $(SUITE) $(SUITE_ARGS)

validate-eval-author-products:
	python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v1.json

validate-candidate-experiment:
	@test -n "$(CANDIDATE_EXPERIMENT)" || (echo "Set CANDIDATE_EXPERIMENT=experiments/approved-candidate.json" && exit 2)
	@test -n "$(SUITE)" || (echo "Set SUITE=evals/flywheel-eval-set-v1.json" && exit 2)
	python3 scripts/validate_candidate_experiment.py "$(CANDIDATE_EXPERIMENT)" --suite "$(SUITE)"
