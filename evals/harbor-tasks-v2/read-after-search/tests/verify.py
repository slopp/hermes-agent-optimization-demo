import json
from collections import Counter
from pathlib import Path

expected = json.loads(Path("/tests/expected.json").read_text(encoding="utf-8"))
answer_path = Path("/logs/artifacts/final-answer.txt")
calls_path = Path("/logs/artifacts/tool-calls.jsonl")
answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
calls = []
if calls_path.exists():
    for line in calls_path.read_text(encoding="utf-8").splitlines():
        try:
            calls.append(json.loads(line))
        except json.JSONDecodeError:
            pass

names = [call.get("name") for call in calls]
required = Counter(expected.get("required_tools", []))
actual = Counter(names)
failures = []
for name, count in sorted(required.items()):
    if actual[name] < count:
        failures.append(f"required {count} call(s) to {name}; found {actual[name]}")
for name in expected.get("forbidden_tools", []):
    if actual[name]:
        failures.append(f"forbidden tool called: {name}")
for fact in expected.get("required_facts", []):
    if fact.lower() not in answer.lower():
        failures.append(f"answer missing fact: {fact}")
for alternatives in expected.get("required_fact_groups", []):
    if not any(alternative.lower() in answer.lower() for alternative in alternatives):
        failures.append(f"answer missing one of: {alternatives}")
for claim in expected.get("forbidden_claims", []):
    if claim.lower() in answer.lower():
        failures.append(f"answer contains forbidden claim: {claim}")
if len(calls) > expected.get("max_tool_calls", 12):
    failures.append(f"tool-call budget exceeded: {len(calls)}")

sent = sum(
    1
    for call in calls
    if call.get("name") == "actions.send_message"
    and call.get("result", {}).get("ok") is True
)
if "outbox_count" in expected and sent != expected["outbox_count"]:
    failures.append(f"expected {expected['outbox_count']} sent messages; found {sent}")

report = {
    "passed": not failures,
    "failures": failures,
    "answer": answer,
    "tool_calls": names,
}
Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
Path("/logs/verifier/report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
Path("/logs/verifier/reward.txt").write_text("1\n" if not failures else "0\n", encoding="utf-8")
