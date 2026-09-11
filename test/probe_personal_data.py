"""Direct personal-data and phone-address persistence probe."""

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

from PAN_SDK import PANPersistenceStore, SovereignIdentity
from PAN_SDK.personal_data import PANPersonalDataStore, PANPhoneAddressRegistry


def run() -> Dict[str, Any]:
    print("=== personal data + phone address reload ===")
    details: Dict[str, Any] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="pan_personal_") as tmpdir:
            base_path = Path(tmpdir)
            identity = SovereignIdentity("PersonalOwner")
            other = SovereignIdentity("PersonalPeer")
            persistence_one = PANPersistenceStore(base_path=base_path)
            store_one = PANPersonalDataStore(
                sovereign_id=identity.identity_hash,
                base_path=base_path / "personal_data",
                persistence=persistence_one,
            )
            phones_one = PANPhoneAddressRegistry(persistence=persistence_one)

            contact = store_one.add_contact(
                display_name="Ada",
                pan_phone_address="pan:test:voice",
                phone_numbers=["+15555550100"],
                email_addresses=["ada@example.pan"],
                tags=["lab"],
            )
            message = store_one.send_message(other.identity_hash, "hello from the lab", message_type="chat")
            call = store_one.log_call(
                caller_sovereign_id=identity.identity_hash,
                recipient_sovereign_id=other.identity_hash,
                call_type="voice",
                direction="outgoing",
                duration_seconds=12,
            )
            prefs = store_one.get_preferences()
            prefs.theme = "light"
            store_one.save_preferences(prefs)
            phone_address = phones_one.assign_phone_address(
                sovereign_id=identity.identity_hash,
                vm_id="vm-lab-1",
                network_hash="netlab",
                identity_motif="motiflab",
            )
            print(f"contact={contact.contact_id[:12]} message={message.message_id[:12]} call={call.call_id[:12]}")
            print(f"phone_address={phone_address} theme={store_one.preferences.theme}")

            snapshot = {
                "contacts": {cid: c.to_dict() for cid, c in store_one.contacts.items()},
                "messages": {mid: m.to_dict() for mid, m in store_one.messages.items()},
                "call_logs": {cid: c.to_dict() for cid, c in store_one.call_logs.items()},
                "preferences": store_one.preferences.to_dict() if store_one.preferences else None,
                "phone_addresses": dict(phones_one.address_map),
            }
            store_one.close()
            persistence_one.close()

            persistence_two = PANPersistenceStore(base_path=base_path)
            store_two = PANPersonalDataStore(
                sovereign_id=identity.identity_hash,
                base_path=base_path / "personal_data",
                persistence=persistence_two,
            )
            phones_two = PANPhoneAddressRegistry(persistence=persistence_two)
            reloaded = {
                "contacts": {cid: c.to_dict() for cid, c in store_two.contacts.items()},
                "messages": {mid: m.to_dict() for mid, m in store_two.messages.items()},
                "call_logs": {cid: c.to_dict() for cid, c in store_two.call_logs.items()},
                "preferences": store_two.preferences.to_dict() if store_two.preferences else None,
                "phone_addresses": dict(phones_two.address_map),
            }
            matches = {}
            all_match = True
            for key, original in snapshot.items():
                matched = original == reloaded[key]
                matches[key] = matched
                print(f"compare {key}: {'MATCH' if matched else 'MISMATCH'} count={len(original) if isinstance(original, dict) else original}")
                if not matched:
                    all_match = False
            details["matches"] = matches
            details["phone_address"] = phone_address
            if not all_match:
                raise AssertionError(f"personal-data reload mismatch: {matches}")
            store_two.close()
            persistence_two.close()
        return {"name": "personal_data", "passed": True, "details": details}
    except Exception as exc:
        print(f"FAIL personal_data: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "personal_data", "passed": False, "error": f"{type(exc).__name__}: {exc}", "details": details}


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
