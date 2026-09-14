#!/bin/sh
# Run one real Hermes/OpenShell-compatible collection case against mock MCP.
# Usage: HERMES_SOURCE=/path/to/hermes-agent NVIDIA_API_KEY=... \
#   scripts/run_hermes_case.sh <case-id> <query> [baseline|candidate]
set -eu

case_id=${1:?case ID is required}
query=${2:?query is required}
arm=${3:-${HERMES_ARM:-baseline}}
demo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
hermes_source=${HERMES_SOURCE:?HERMES_SOURCE must point to a Hermes source checkout}
model=${HERMES_MODEL:-nvidia/nemotron-3.5-lightning-30b-a3b}
provider=${HERMES_PROVIDER:-nvidia}
base_url=${HERMES_BASE_URL:-}
tool_catalog=${HERMES_TOOL_CATALOG:-extended}
ignore_rules=${HERMES_DEMO_IGNORE_RULES:-1}
wall_timeout_seconds=${HERMES_RUN_TIMEOUT_SECONDS:-180}
collection_mode=${HERMES_COLLECTION_MODE:-local-hermes}
inference_route=${HERMES_INFERENCE_ROUTE:-}

if [ ! -d "$hermes_source" ]; then
  echo "HERMES_SOURCE is not a directory: $hermes_source" >&2
  exit 2
fi
if [ "$provider" = custom ] && [ -z "$base_url" ]; then
  echo "HERMES_BASE_URL is required when HERMES_PROVIDER=custom" >&2
  exit 2
fi
if [ "$provider" = custom ]; then
  if [ -z "${INFERENCE_HUB_API_KEY:-}" ]; then
    echo "INFERENCE_HUB_API_KEY is required when HERMES_PROVIDER=custom." >&2
    exit 2
  fi
elif [ -z "${NVIDIA_API_KEY:-}" ]; then
  echo "NVIDIA_API_KEY is required for the native Build provider." >&2
  exit 2
fi
if [ -z "$inference_route" ]; then
  if [ "$provider" = custom ]; then
    inference_route=hub-test
  else
    inference_route=build
  fi
fi
case "$tool_catalog" in
  focused|extended) ;;
  *)
    echo "HERMES_TOOL_CATALOG must be focused or extended, got: $tool_catalog" >&2
    exit 2
    ;;
esac
case "$ignore_rules" in
  0|1) ;;
  *)
    echo "HERMES_DEMO_IGNORE_RULES must be 0 or 1, got: $ignore_rules" >&2
    exit 2
    ;;
esac
case "$wall_timeout_seconds" in
  *[!0-9]*|'')
    echo "HERMES_RUN_TIMEOUT_SECONDS must be a positive integer, got: $wall_timeout_seconds" >&2
    exit 2
    ;;
esac
if [ "$wall_timeout_seconds" -lt 1 ]; then
  echo "HERMES_RUN_TIMEOUT_SECONDS must be at least 1" >&2
  exit 2
fi

case "$arm" in
  baseline)
    prompt_file="$demo_root/profiles/baseline-system-prompt.md"
    ;;
  candidate)
    prompt_file="$demo_root/profiles/optimized-system-prompt.md"
    ;;
  *)
    echo "arm must be baseline or candidate, got: $arm" >&2
    exit 2
    ;;
esac

if [ "$arm" = candidate ]; then
  candidate_manifest=${HERMES_CANDIDATE_EXPERIMENT:?HERMES_CANDIDATE_EXPERIMENT must point to an approved candidate experiment}
  trace_suite=${HERMES_TRACE_DERIVED_SUITE:?HERMES_TRACE_DERIVED_SUITE must point to an approved trace-derived suite}
  python3 "$demo_root/scripts/validate_candidate_experiment.py" \
    "$candidate_manifest" --suite "$trace_suite" >/dev/null
fi

safe_case_id=$(printf '%s' "$case_id" | tr -cd 'A-Za-z0-9_.-')
if [ -z "$safe_case_id" ]; then
  echo "case ID must contain at least one letter, number, dot, underscore, or hyphen" >&2
  exit 2
fi

run_dir=${RUN_DIRECTORY:-"$demo_root/.runs/$arm/$safe_case_id"}
python3 "$demo_root/scripts/prepare_hermes_run.py" \
  --run-dir "$run_dir" \
  --model "$model" \
  --provider "$provider" \
  --base-url "$base_url" \
  --tool-catalog "$tool_catalog" \
  --system-prompt-file "$prompt_file" >/dev/null
mkdir -p "$run_dir/relay/atof" "$run_dir/relay/atif"
if [ "$ignore_rules" = 1 ]; then
  provenance_ignore_rules_arg='--ignore-rules'
else
  provenance_ignore_rules_arg=''
fi
python3 "$demo_root/scripts/write_run_provenance.py" \
  --output "$run_dir/collection-provenance.json" \
  --fixture "$demo_root/fixtures/world-v1.json" \
  --profile "$prompt_file" \
  --config "$run_dir/hermes-home/config.yaml" \
  --hermes-source "$hermes_source" \
  --arm "$arm" \
  --provider "$provider" \
  --model "$model" \
  --base-url "$base_url" \
  --tool-catalog "$tool_catalog" \
  --wall-timeout-seconds "$wall_timeout_seconds" \
  --collection-mode "$collection_mode" \
  --inference-route "$inference_route" \
  $provenance_ignore_rules_arg >/dev/null

export HERMES_HOME="$run_dir/hermes-home"
export HERMES_NEMO_RELAY_ATOF_ENABLED=1
export HERMES_NEMO_RELAY_ATOF_OUTPUT_DIRECTORY="$run_dir/relay/atof"
export HERMES_NEMO_RELAY_ATOF_FILENAME="${safe_case_id}-events.jsonl"
export HERMES_NEMO_RELAY_ATOF_MODE=overwrite
export HERMES_NEMO_RELAY_ATIF_ENABLED=1
export HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY="$run_dir/relay/atif"
export HERMES_NEMO_RELAY_ATIF_FILENAME_TEMPLATE="${safe_case_id}-trajectory-{session_id}.json"
export HERMES_NEMO_RELAY_ATIF_AGENT_NAME=Hermes-PA-style-mock
export HERMES_NEMO_RELAY_ATIF_AGENT_VERSION="${arm}-local-collection"
export HERMES_NEMO_RELAY_ATIF_MODEL_NAME="$model"

# Hermes' generic custom provider reads OPENAI_API_KEY. Map only the separate
# Hub test credential into that process; never write either credential into the
# isolated profile.
if [ "$provider" = custom ]; then
  # Do not let an unrelated host OPENAI_API_KEY override the explicit Hub test
  # route; that produces a misleading authentication failure. Hermes' bare
  # custom resolver also derives NVIDIA_API_KEY from inference-api.nvidia.com,
  # so scope the Hub credential to that resolver name for this child only.
  export OPENAI_API_KEY="$INFERENCE_HUB_API_KEY"
  export NVIDIA_API_KEY="$INFERENCE_HUB_API_KEY"
fi

cd "$hermes_source"
# Hermes may emit reasoning despite --quiet for some providers. Keep the
# complete, fictional CLI transcript beside its ignored Relay artifacts rather
# than mixing it into a collection runner's stdout. On failure, report the
# local path without copying trace content to the terminal.
cli_log="$run_dir/hermes-cli.log"
if [ "$ignore_rules" = 1 ]; then
  ignore_rules_arg='--ignore-rules'
else
  ignore_rules_arg=''
fi
python3 "$demo_root/scripts/run_with_timeout.py" \
  --seconds "$wall_timeout_seconds" -- \
  uv run --extra mcp hermes chat \
  --query "$query" \
  --provider "$provider" \
  --model "$model" \
  --toolsets pa_style_enterprise \
  --max-turns "${MAX_TURNS:-8}" \
  $ignore_rules_arg \
  --quiet >"$cli_log" 2>&1 || {
    exit_status=$?
    echo "Hermes run failed (exit $exit_status); inspect ignored local log: $cli_log" >&2
    exit "$exit_status"
  }

printf '%s\n' "Relay artifacts ($arm): $run_dir/relay"
