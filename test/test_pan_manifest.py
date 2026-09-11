"""Direct ModelManifest verification probe."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import ModelManifest, SovereignIdentity


def run() -> Dict[str, Any]:
    print("=== manifest verification ===")
    details: Dict[str, Any] = {}
    try:
        distributor_identity = SovereignIdentity("Distributor")
        model_identity = SovereignIdentity("Model")
        manifest = ModelManifest(
            model_name="gemma3-4b-it.lacka",
            model_hash="abc123deadbeef",
            model_public_key_pem=model_identity.get_public_key_pem(),
            creator_identity=distributor_identity,
        )
        rehydrated = ModelManifest.from_dict(manifest.to_dict())
        valid = rehydrated.verify_manifest(
            distributor_identity.get_public_key_pem(),
            expected_creator_identity_hash=distributor_identity.identity_hash,
        )
        print(f"valid_manifest={valid}")
        details["valid"] = valid
        if not valid:
            raise AssertionError("expected valid manifest verification")

        tampered = ModelManifest.from_dict(manifest.to_dict())
        tampered.content["model_hash"] = "tampered"
        tampered_valid = tampered.verify_manifest(
            distributor_identity.get_public_key_pem(),
            expected_creator_identity_hash=distributor_identity.identity_hash,
        )
        print(f"tampered_manifest={tampered_valid}")
        details["tampered"] = tampered_valid
        if tampered_valid:
            raise AssertionError("tampered manifest must not verify")

        wrong_key = ModelManifest.from_dict(manifest.to_dict())
        intruder = SovereignIdentity("Intruder")
        wrong = wrong_key.verify_manifest(intruder.get_public_key_pem())
        print(f"wrong_key_manifest={wrong}")
        details["wrong_key"] = wrong
        if wrong:
            raise AssertionError("wrong-key manifest must not verify")

        return {"name": "manifest", "passed": True, "details": details}
    except Exception as exc:
        print(f"FAIL manifest: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "manifest", "passed": False, "error": f"{type(exc).__name__}: {exc}", "details": details}


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
