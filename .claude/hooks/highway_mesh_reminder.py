#!/usr/bin/env python3
"""PostToolUse: after touching the highway/telecom border, restate the unresolved
cross-host mesh status so it isn't lost between turns or sessions.

Provenance: cross-device probe 2026-09-16/17 -- both hosts remountable, same
HEAD, separate in-env gates PASS, dual installer boots PASS, but
phone_ready/adb_proven FAIL on both -> sealed A->B stayed
NOT_ATTEMPTED_UNTIL_READY. Heartbeats prove pin reachability only, not a mesh
exchange.
"""
import json
import sys

WATCHED_SUFFIXES = (
    "telecom/phone_orchestrator.py",
    "security/planetary_highway.py",
)

REMINDER = (
    "Highway status: cross-host PAN mesh (sealed device A -> device B exchange) is "
    "UNVERIFIED. Last cross-device probe: separate in-env gates PASS on both hosts and "
    "dual installer boots PASS, but phone_ready/adb_proven FAIL on both, so sealed A->B "
    "stays NOT_ATTEMPTED_UNTIL_READY. Heartbeats only prove pin reachability, not a mesh "
    "exchange. Do not report cross-device PAN talk as proven from this file alone -- the "
    "blocker is upstream in qcow2->ADB boot, then a FAIL-capable sealed exchange."
)


def main() -> int:
    data = json.load(sys.stdin)
    path = (
        data.get("tool_response", {}).get("filePath")
        or data.get("tool_input", {}).get("file_path")
        or ""
    )
    if not any(path.endswith(suffix) for suffix in WATCHED_SUFFIXES):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": REMINDER,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
