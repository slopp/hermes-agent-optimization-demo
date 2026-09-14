"""Lossless-enough ATIF adapter for the standalone NeMo Insights CLI.

Insights intentionally accepts one canonical trace contract rather than every
producer's wire format.  This module maps the fields Relay actually records;
it does not infer failures, timings, or provenance that ATIF did not capture.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any


def _tool_catalog(steps: Iterable[dict[str, Any]]) -> dict[str, Any]:
    catalog: dict[str, Any] = {}
    for step in steps:
        request = step.get("extra", {}).get("llm_request", {})
        for item in request.get("tools", []):
            function = item.get("function", {})
            name = function.get("name")
            parameters = function.get("parameters")
            if isinstance(name, str) and isinstance(parameters, dict):
                catalog.setdefault(name, parameters)
    return catalog


def atif_to_insights_trace(
    trajectory: dict[str, Any], *, logical_case_id: str | None = None
) -> dict[str, Any]:
    """Convert one Relay ATIF-v1 trajectory to canonical Insights Trace JSON."""
    schema_version = str(trajectory.get("schema_version", ""))
    if not schema_version.startswith("ATIF-v1"):
        raise ValueError("expected an ATIF-v1 trajectory")

    trace_id = trajectory.get("trajectory_id") or trajectory.get("session_id")
    if not isinstance(trace_id, str) or not trace_id:
        raise ValueError("ATIF trajectory needs a trajectory_id or session_id")

    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        raise TypeError("ATIF trajectory steps must be a list")

    spans: list[dict[str, Any]] = []
    latest_user_text: str | None = None
    final_answer = ""
    tool_index = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        message = step.get("message")
        if step.get("source") == "user" and isinstance(message, str) and message.strip():
            latest_user_text = message
        if step.get("source") == "agent" and isinstance(message, str) and message.strip():
            final_answer = message

        results_by_call: dict[str, list[dict[str, Any]]] = {}
        observation = step.get("observation")
        if isinstance(observation, dict):
            for result in observation.get("results", []):
                if not isinstance(result, dict):
                    continue
                source_call_id = result.get("source_call_id")
                if isinstance(source_call_id, str):
                    results_by_call.setdefault(source_call_id, []).append(result)

        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            call_id = call.get("tool_call_id")
            name = call.get("function_name")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("ATIF tool call is missing tool_call_id")
            if not isinstance(name, str) or not name:
                raise ValueError(f"ATIF tool call {call_id!r} is missing function_name")
            arguments = call.get("arguments", {})
            matches = results_by_call.get(call_id, [])
            output: Any
            if len(matches) == 1:
                output = matches[0].get("content")
            elif len(matches) > 1:
                output = [result.get("content") for result in matches]

            tool_call: dict[str, Any] = {
                "call_id": call_id,
                "index": tool_index,
                "result_count": len(matches),
                "prior_user_text": latest_user_text,
            }
            if len(matches) == 1 and isinstance(matches[0].get("source_call_id"), str):
                tool_call["result_id"] = matches[0]["source_call_id"]

            span: dict[str, Any] = {
                "id": call_id,
                "kind": "TOOL",
                "input": arguments,
                "tool_name": name,
                "tool_call": tool_call,
                "attributes": {
                    "source_pointer": {
                        "atif_trace_id": trace_id,
                        "step_id": step.get("step_id"),
                    },
                    "call_extra": call.get("extra", {}),
                },
            }
            timestamp = step.get("timestamp")
            if isinstance(timestamp, str):
                span["start_time"] = timestamp
            if matches:
                span["output"] = output
                span["attributes"]["result_extra"] = [
                    result.get("extra", {}) for result in matches
                ]
            spans.append(span)
            tool_index += 1

    attributes: dict[str, Any] = {
        "complete_provenance_context": False,
        "source_pointer": {
            "format": schema_version,
            "session_id": trajectory.get("session_id"),
            "trajectory_id": trajectory.get("trajectory_id"),
        },
        "agent": trajectory.get("agent", {}),
        "tool_catalog": _tool_catalog(steps),
        "final_answer": final_answer,
        "final_metrics": trajectory.get("final_metrics", {}),
    }
    if logical_case_id:
        attributes["logical_case_id"] = logical_case_id

    return {"id": trace_id, "root_spans": spans, "aggregate": {}, "attributes": attributes}


def _scope_pairs(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for event in events:
        uuid = event.get("uuid")
        phase = event.get("scope_category")
        if event.get("kind") == "scope" and isinstance(uuid, str) and phase in {"start", "end"}:
            pairs[uuid][phase] = event
    return pairs


def _descendants(root: str, children: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    pending = list(children.get(root, []))
    while pending:
        event = pending.pop(0)
        found.append(event)
        uuid = event.get("uuid")
        if isinstance(uuid, str):
            pending.extend(children.get(uuid, []))
    return found


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    normalized = re.sub(r"(\.\d{6})\d+([+-]\d{2}:\d{2})$", r"\1\2", normalized)
    return datetime.fromisoformat(normalized)


def atof_events_to_insights_traces(
    events: list[dict[str, Any]],
    *,
    prompt_case_ids: Mapping[str, str] | None = None,
    case_required_signals: Mapping[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Group completed Hermes turns in Relay ATOF into canonical Insights traces."""
    pairs = _scope_pairs(events)
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("scope_category") != "start":
            continue
        parent = event.get("parent_uuid")
        if isinstance(parent, str):
            children[parent].append(event)

    traces: list[dict[str, Any]] = []
    for turn_id, turn_pair in pairs.items():
        start = turn_pair.get("start")
        end = turn_pair.get("end")
        if not start or not end or start.get("name") != "hermes.turn":
            continue
        descendants = _descendants(turn_id, children)
        llm_pairs = [
            pairs[event["uuid"]]
            for event in descendants
            if event.get("category") == "llm" and "end" in pairs.get(event.get("uuid"), {})
        ]
        prompt = ""
        catalog: dict[str, Any] = {}
        model: str | None = None
        final_answer = ""
        input_tokens = cached_tokens = output_tokens = 0
        provider_errors: list[dict[str, str]] = []
        for pair in llm_pairs:
            start_data = pair["start"].get("data")
            request = start_data.get("content", {}) if isinstance(start_data, dict) else {}
            for message in request.get("messages", []) if isinstance(request, dict) else []:
                if message.get("role") == "user" and isinstance(message.get("content"), str):
                    prompt = message["content"]
            for item in request.get("tools", []) if isinstance(request, dict) else []:
                function = item.get("function", {})
                if isinstance(function.get("name"), str) and isinstance(function.get("parameters"), dict):
                    catalog.setdefault(function["name"], function["parameters"])
            end_data = pair["end"].get("data")
            response = end_data if isinstance(end_data, dict) else {}
            end_metadata = pair["end"].get("metadata", {})
            if isinstance(end_metadata, dict) and end_metadata.get("error.type"):
                provider_errors.append(
                    {
                        "error_type": str(end_metadata.get("error.type")),
                        "exception_type": str(end_metadata.get("exception.type") or ""),
                    }
                )
            if isinstance(response.get("model"), str):
                model = response["model"]
            usage = response.get("usage", {})
            if isinstance(usage, dict):
                prompt_count = int(usage.get("prompt_tokens") or 0)
                cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
                input_tokens += max(0, prompt_count - cached)
                cached_tokens += cached
                output_tokens += int(usage.get("completion_tokens") or 0)
            for choice in response.get("choices", []) if isinstance(response, dict) else []:
                content = (choice.get("message") or {}).get("content")
                if isinstance(content, str) and content.strip():
                    final_answer = content

        case_id = None
        if prompt_case_ids:
            case_id = prompt_case_ids.get(prompt)
            if case_id is None:
                # Hermes appends a runtime-context block to the recorded user
                # message. Match only an exact prompt prefix followed by that
                # delimiter so case attribution remains deterministic.
                for matrix_prompt, matrix_case_id in prompt_case_ids.items():
                    if prompt.startswith(f"{matrix_prompt}\n\nNemoClaw runtime context:"):
                        case_id = matrix_case_id
                        break
        spans: list[dict[str, Any]] = []
        for event in descendants:
            if event.get("category") != "tool" or event.get("scope_category") != "start":
                continue
            uuid = event.get("uuid")
            pair = pairs.get(uuid, {})
            terminal = pair.get("end")
            metadata = event.get("metadata", {})
            call_id = metadata.get("tool_call_id") if isinstance(metadata, dict) else None
            span: dict[str, Any] = {
                "id": uuid,
                "kind": "TOOL",
                "input": event.get("data"),
                "tool_name": event.get("name"),
                "tool_call": {
                    "call_id": call_id,
                    "index": len(spans),
                    "result_count": 1 if terminal else 0,
                    "prior_user_text": prompt or None,
                },
                "attributes": {
                    "source_pointer": {"atof_turn_id": turn_id, "scope_uuid": uuid},
                    "start_metadata": metadata,
                },
            }
            if terminal:
                span["output"] = terminal.get("data")
                span["end_time"] = terminal.get("timestamp")
                span["attributes"]["end_metadata"] = terminal.get("metadata", {})
                span["tool_call"]["result_id"] = call_id
                status = terminal.get("metadata", {}).get("otel.status_code")
                outcome = terminal.get("data", {}).get("outcome") if isinstance(terminal.get("data"), dict) else None
                if status not in {None, "OK"}:
                    span["error"] = str(status)
                elif outcome not in {None, "success"}:
                    span["error"] = str(outcome)
            if isinstance(event.get("timestamp"), str):
                span["start_time"] = event["timestamp"]
            spans.append(span)

        started = _timestamp(start.get("timestamp"))
        ended = _timestamp(end.get("timestamp"))
        aggregate: dict[str, Any] = {
            "token_counts": {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "output_tokens": output_tokens,
            }
        }
        if started and ended:
            aggregate["latency_ms"] = (ended - started).total_seconds() * 1000
        turn_end_data = end.get("data")
        turn_outcome = (
            turn_end_data.get("outcome") if isinstance(turn_end_data, dict) else None
        )
        attributes = {
            "complete_provenance_context": False,
            "source_pointer": {"format": "ATOF", "turn_id": turn_id},
            "logical_case_id": case_id or turn_id,
            "prompt": prompt,
            "final_answer": final_answer,
            "tool_catalog": catalog,
            "model": model,
            "turn_outcome": turn_outcome,
            "provider_errors": provider_errors,
            # A transient provider error that Hermes retries successfully does
            # not invalidate the observed behavior. It remains recorded for
            # reliability/latency analysis. Exclude only provider-caused
            # terminal turns from quality aggregates.
            "infrastructure_valid": not provider_errors or turn_outcome != "failed",
        }
        if case_id and case_required_signals and case_id in case_required_signals:
            required = Counter(case_required_signals[case_id])
            observed_names = [_canonical_pa_tool_name(span.get("tool_name")) for span in spans]
            observed = Counter(name for name in observed_names if name)
            matched = sum(min(count, observed.get(name, 0)) for name, count in required.items())
            total = sum(required.values())
            missing = [name for name, count in required.items() for _ in range(max(0, count - observed.get(name, 0)))]
            local_names = {"execute_code", "read_file", "search_files", "session_search", "terminal", "write_file"}
            call_count = len(spans)
            attributes["metrics"] = {
                "required_signal_coverage": matched / total if total else 1.0,
                "enterprise_tool_share": sum(name is not None for name in observed_names) / call_count if call_count else 0.0,
                "local_or_session_call_share": sum(span.get("tool_name") in local_names for span in spans) / call_count if call_count else 0.0,
            }
            attributes["trajectory_contract"] = {
                "required_signals": list(case_required_signals[case_id]),
                "missing_signals": missing,
            }
            if missing:
                attributes["observed_verdict"] = "missing required enterprise evidence"
        traces.append({"id": turn_id, "root_spans": spans, "aggregate": aggregate, "attributes": attributes})
    return traces


def _canonical_pa_tool_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    prefix = "mcp__pa_style_enterprise__"
    if not value.startswith(prefix):
        return None
    short = value[len(prefix) :]
    domain, separator, operation = short.partition("_")
    return f"{domain}.{operation}" if separator else short
