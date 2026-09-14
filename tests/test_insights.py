import unittest

from pa_style_mock_mcp.insights import atif_to_insights_trace, atof_events_to_insights_traces


class InsightsAdapterTests(unittest.TestCase):
    def test_maps_recorded_call_result_and_catalog_without_inventing_error(self) -> None:
        atif = {
            "schema_version": "ATIF-v1.7",
            "trajectory_id": "trace-1",
            "session_id": "session-1",
            "agent": {"name": "Hermes"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "user",
                    "message": "Find the packet",
                    "extra": {
                        "llm_request": {
                            "tools": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "files_search",
                                        "parameters": {"type": "object"},
                                    },
                                }
                            ]
                        }
                    },
                },
                {
                    "step_id": 2,
                    "source": "agent",
                    "message": "",
                    "timestamp": "2026-09-11T12:00:00+00:00",
                    "tool_calls": [
                        {
                            "tool_call_id": "call-1",
                            "function_name": "files_search",
                            "arguments": {"query": "packet"},
                        }
                    ],
                    "observation": {
                        "results": [
                            {"source_call_id": "call-1", "content": '{"ok":true}'}
                        ]
                    },
                },
                {"step_id": 3, "source": "agent", "message": "Found it."},
            ],
        }

        trace = atif_to_insights_trace(atif, logical_case_id="packet-case")

        self.assertEqual(trace["id"], "trace-1")
        self.assertEqual(trace["attributes"]["logical_case_id"], "packet-case")
        self.assertEqual(trace["attributes"]["final_answer"], "Found it.")
        self.assertEqual(trace["attributes"]["tool_catalog"], {"files_search": {"type": "object"}})
        span = trace["root_spans"][0]
        self.assertEqual(span["tool_call"]["result_count"], 1)
        self.assertEqual(span["tool_call"]["prior_user_text"], "Find the packet")
        self.assertEqual(span["output"], '{"ok":true}')
        self.assertNotIn("error", span)

    def test_preserves_missing_result_as_result_count_zero(self) -> None:
        atif = {
            "schema_version": "ATIF-v1.7",
            "session_id": "session-1",
            "steps": [
                {
                    "source": "agent",
                    "tool_calls": [
                        {"tool_call_id": "call-1", "function_name": "search", "arguments": {}}
                    ],
                }
            ],
        }

        span = atif_to_insights_trace(atif)["root_spans"][0]

        self.assertEqual(span["tool_call"]["result_count"], 0)
        self.assertNotIn("output", span)

    def test_groups_completed_atof_turn_and_joins_tool_scope(self) -> None:
        events = [
            {"kind": "scope", "scope_category": "start", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:00+00:00"},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "timestamp": "2026-09-11T12:00:01+00:00", "data": {"content": {"messages": [{"role": "user", "content": "Find it"}], "tools": [{"function": {"name": "search", "parameters": {"type": "object"}}}]}}},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "timestamp": "2026-09-11T12:00:02+00:00", "data": {"model": "nemotron", "usage": {"prompt_tokens": 10, "prompt_tokens_details": {"cached_tokens": 4}, "completion_tokens": 3}, "choices": [{"message": {"content": "Found it"}}]}},
            {"kind": "scope", "scope_category": "start", "category": "tool", "name": "search", "uuid": "tool", "parent_uuid": "turn", "timestamp": "2026-09-11T12:00:02+00:00", "data": {"query": "it"}, "metadata": {"tool_call_id": "call-1"}},
            {"kind": "scope", "scope_category": "end", "category": "tool", "name": "search", "uuid": "tool", "parent_uuid": "turn", "timestamp": "2026-09-11T12:00:03+00:00", "data": {"ok": True}, "metadata": {"tool_call_id": "call-1", "otel.status_code": "OK"}},
            {"kind": "scope", "scope_category": "end", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:04+00:00", "data": {"outcome": "success"}},
        ]

        trace = atof_events_to_insights_traces(
            events,
            prompt_case_ids={"Find it": "find"},
            case_required_signals={"find": ["chat.search"]},
        )[0]

        self.assertEqual(trace["attributes"]["logical_case_id"], "find")
        self.assertEqual(trace["attributes"]["observed_verdict"], "missing required enterprise evidence")
        self.assertEqual(trace["attributes"]["metrics"]["required_signal_coverage"], 0.0)
        self.assertEqual(trace["attributes"]["final_answer"], "Found it")
        self.assertEqual(trace["aggregate"]["latency_ms"], 4000)
        self.assertEqual(trace["aggregate"]["token_counts"], {"input_tokens": 6, "cached_input_tokens": 4, "output_tokens": 3})
        self.assertEqual(trace["root_spans"][0]["tool_call"]["result_id"], "call-1")
        self.assertTrue(trace["attributes"]["infrastructure_valid"])
        self.assertEqual(trace["attributes"]["provider_errors"], [])

    def test_marks_turn_with_recorded_provider_error_as_invalid(self) -> None:
        events = [
            {"kind": "scope", "scope_category": "start", "category": "function", "name": "hermes.turn", "uuid": "turn"},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": {}},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": None, "metadata": {"error.type": "rate_limit", "exception.type": "RateLimitError"}},
            {"kind": "scope", "scope_category": "end", "category": "function", "name": "hermes.turn", "uuid": "turn", "data": {"outcome": "failed"}},
        ]

        trace = atof_events_to_insights_traces(events)[0]

        self.assertFalse(trace["attributes"]["infrastructure_valid"])
        self.assertEqual(
            trace["attributes"]["provider_errors"],
            [{"error_type": "rate_limit", "exception_type": "RateLimitError"}],
        )

    def test_recovered_provider_error_remains_valid_and_recorded(self) -> None:
        events = [
            {"kind": "scope", "scope_category": "start", "category": "function", "name": "hermes.turn", "uuid": "turn"},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "failed", "parent_uuid": "turn", "data": {}},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "failed", "parent_uuid": "turn", "data": None, "metadata": {"error.type": "rate_limit"}},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "ok", "parent_uuid": "turn", "data": {}},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "ok", "parent_uuid": "turn", "data": {"choices": [{"message": {"content": "done"}}]}},
            {"kind": "scope", "scope_category": "end", "category": "function", "name": "hermes.turn", "uuid": "turn", "data": {"outcome": "success"}},
        ]

        trace = atof_events_to_insights_traces(events)[0]

        self.assertTrue(trace["attributes"]["infrastructure_valid"])
        self.assertEqual(len(trace["attributes"]["provider_errors"]), 1)

    def test_tolerates_llm_scope_with_null_payload(self) -> None:
        events = [
            {"kind": "scope", "scope_category": "start", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:00+00:00"},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": None},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": None},
            {"kind": "scope", "scope_category": "end", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:01+00:00", "data": None},
        ]

        trace = atof_events_to_insights_traces(events)[0]

        self.assertEqual(trace["attributes"]["final_answer"], "")
        self.assertEqual(trace["root_spans"], [])

    def test_matches_matrix_prompt_before_nemoclaw_runtime_context(self) -> None:
        events = [
            {"kind": "scope", "scope_category": "start", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:00+00:00"},
            {"kind": "scope", "scope_category": "start", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": {"content": {"messages": [{"role": "user", "content": "Find it\n\nNemoClaw runtime context:\n- sandbox"}]}}},
            {"kind": "scope", "scope_category": "end", "category": "llm", "name": "openai.chat_completions", "uuid": "llm", "parent_uuid": "turn", "data": {}},
            {"kind": "scope", "scope_category": "end", "category": "function", "name": "hermes.turn", "uuid": "turn", "timestamp": "2026-09-11T12:00:01+00:00", "data": {}},
        ]

        trace = atof_events_to_insights_traces(events, prompt_case_ids={"Find it": "find"})[0]

        self.assertEqual(trace["attributes"]["logical_case_id"], "find")


if __name__ == "__main__":
    unittest.main()
