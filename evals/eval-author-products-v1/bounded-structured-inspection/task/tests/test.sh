#!/bin/sh
python - <<'PY'
import json
from pathlib import Path

answer_path = Path("/logs/artifacts/answer.json")
expected_path = Path("/tests/expected.json")
try:
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    passed = isinstance(answer, dict) and all(answer.get(key) == value for key, value in expected.items())
except (OSError, UnicodeError, json.JSONDecodeError):
    passed = False
Path("/logs/verifier/reward.txt").write_text("1\n" if passed else "0\n", encoding="utf-8")
PY
