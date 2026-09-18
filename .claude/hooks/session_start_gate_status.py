#!/usr/bin/env python3
"""SessionStart: orient on the last run_pan_gate.py result instead of booting blind."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    pattern = os.path.join(ROOT, "results", "pan_gate_*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not files:
        return 0
    latest = files[-1]
    try:
        with open(latest) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return 0
    status = "PASS" if data.get("passed") else "FAIL"
    ts = data.get("timestamp", "unknown")
    msg = (
        f"PAN SDK gate: last run_pan_gate.py was {status} at {ts} "
        f"({os.path.basename(latest)}). This covers in-env slices only -- cross-host "
        f"PAN mesh (highway A->B sealed exchange) is separately UNVERIFIED."
    )
    print(json.dumps({
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
