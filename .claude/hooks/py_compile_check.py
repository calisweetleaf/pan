#!/usr/bin/env python3
"""PostToolUse: compile-check a just-edited .py file. Fail loud, block the turn."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"


def main() -> int:
    data = json.load(sys.stdin)
    path = (
        data.get("tool_response", {}).get("filePath")
        or data.get("tool_input", {}).get("file_path")
        or ""
    )
    if not path.endswith(".py"):
        return 0
    file_path = Path(path)
    if not file_path.is_file():
        return 0
    result = subprocess.run(
        [PYTHON, "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(json.dumps({
            "decision": "block",
            "reason": f"Highway gate: py_compile failed for {path}\n{result.stderr.strip()}",
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
