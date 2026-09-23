#!/bin/sh
set -eu
mkdir -p /logs/artifacts
python - <<'PY'
import json
from pathlib import Path
oracle = json.loads(Path("/solution/oracle.json").read_text())
Path("/logs/artifacts/final-answer.txt").write_text(oracle["answer"])
with Path("/logs/artifacts/tool-calls.jsonl").open("w") as stream:
    for call in oracle["calls"]:
        stream.write(json.dumps(call) + "\n")
PY
