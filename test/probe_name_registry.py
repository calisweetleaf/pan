"""Direct PANNameRegistry persistence probe."""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import DHTNode, PANPersistenceStore, SovereignIdentity


def run() -> Dict[str, Any]:
    print("=== name registry persistence ===")
    details: Dict[str, Any] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="pan_names_") as tmpdir:
            storage_path = Path(tmpdir)
            identity = SovereignIdentity("NameNode")
            stranger = SovereignIdentity("Stranger")
            persistence_one = PANPersistenceStore(base_path=storage_path)
            node_one = DHTNode(identity, persistence=persistence_one)

            registered = node_one.name_registry.register_name(
                "testname",
                identity.identity_hash,
                "http://test.pan",
            )
            print(f"register testname -> {registered}")
            details["registered"] = registered
            if not registered:
                raise AssertionError("register_name(testname) failed")

            invalid = node_one.name_registry.register_name("NO", identity.identity_hash)
            print(f"register invalid NO -> {invalid}")
            details["invalid_rejected"] = invalid is False
            if invalid:
                raise AssertionError("invalid name must not register")

            unauthorized = node_one.name_registry.deregister_name("testname", stranger.identity_hash)
            print(f"unauthorized deregister -> {unauthorized}")
            details["unauthorized_rejected"] = unauthorized is False
            if unauthorized:
                raise AssertionError("unauthorized deregister must fail")

            persisted = persistence_one.get_name("testname")
            print(f"get_name after register: active={persisted.get('active') if persisted else None}")
            details["persisted_active"] = bool(persisted and persisted.get("active") is True)
            if not persisted or persisted.get("active") is not True:
                raise AssertionError("name was not written to kv_state")

            persistence_one.close()

            persistence_two = PANPersistenceStore(base_path=storage_path)
            node_two = DHTNode(identity, persistence=persistence_two)
            resolved = node_two.name_registry.resolve_name("testname")
            loaded = node_two.name_registry.load_name_from_db("testname")
            print(f"hydrated resolve={resolved is not None} load_name_from_db={loaded is not None}")
            print(f"hydrated names={list(node_two.name_registry.name_registry)}")
            details["hydrated_name"] = resolved["name"] if resolved else None
            details["hydrated_target"] = resolved["target_identity"] if resolved else None
            if resolved is None or loaded is None:
                raise AssertionError("name did not hydrate after reopen")
            if resolved["target_identity"] != identity.identity_hash:
                raise AssertionError("hydrated target identity mismatch")
            if loaded["name"] != "testname":
                raise AssertionError("load_name_from_db mismatch")

            missing = persistence_two.get_name("no-such-name")
            print(f"get_name missing -> {missing}")
            details["missing_is_none"] = missing is None

            try:
                persistence_two.store_name({"target_identity": identity.identity_hash})
            except ValueError as exc:
                print(f"store_name missing name key raised {exc}")
                details["store_name_fail_loud"] = True
            else:
                raise AssertionError("store_name must fail loud without a name key")

            persistence_two.close()
        return {"name": "name_registry", "passed": True, "details": details}
    except Exception as exc:
        print(f"FAIL name_registry: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "name_registry", "passed": False, "error": f"{type(exc).__name__}: {exc}", "details": details}


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
