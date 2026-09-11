"""Direct consumer for the Nostr-inspired email/social overlay.

Real tempdir SQLite relays + SovereignFirewall ledger. No mocks.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import PANPersistenceStore, SovereignCommunicator, SovereignIdentity
from PAN_SDK.email_social import (
    EmailSocialBlocked,
    EmailSocialCryptoError,
    EmailSocialError,
    EmailSocialNode,
    EmailSocialRelayError,
    reject_legacy_routing,
    seal_plaintext,
)
from security.sovereign_firewall import InspectionLane, SovereignFirewall


class CheckFailure(Exception):
    """A named email/social check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _pair(tmpdir: str, name_a: str, name_b: str) -> tuple[EmailSocialNode, EmailSocialNode, SovereignFirewall, SovereignFirewall]:
    """Open two overlay nodes with independent stores, firewalls, and relays."""
    ident_a = SovereignIdentity(name_a)
    ident_b = SovereignIdentity(name_b)
    store_a = PANPersistenceStore(base_path=Path(tmpdir) / "a")
    store_b = PANPersistenceStore(base_path=Path(tmpdir) / "b")
    fw_a = SovereignFirewall(Path(tmpdir) / "fw_a.sqlite")
    fw_b = SovereignFirewall(Path(tmpdir) / "fw_b.sqlite")
    node_a = EmailSocialNode(ident_a, store_a, fw_a)
    node_b = EmailSocialNode(ident_b, store_b, fw_b)
    node_a.add_peer_relay(node_b.relay)
    node_b.add_peer_relay(node_a.relay)
    return node_a, node_b, fw_a, fw_b


def _close_pair(
    node_a: EmailSocialNode,
    node_b: EmailSocialNode,
    fw_a: SovereignFirewall,
    fw_b: SovereignFirewall,
) -> None:
    """Close sqlite handles so Windows can delete the tempdir."""
    fw_a.close()
    fw_b.close()
    node_a.persistence.close()
    node_b.persistence.close()


def check_sealed_mail_across_relays(details: dict[str, object]) -> None:
    """A sends sealed mail via two relays; B decrypts; a stranger cannot."""
    with tempfile.TemporaryDirectory(prefix="mail_seal_") as tmpdir:
        node_a, node_b, fw_a, fw_b = _pair(tmpdir, "MailAlice", "MailBob")
        stranger = SovereignIdentity("Stranger")
        try:
            published = node_a.send_mail(
                recipient=node_b.identity,
                subject="treasury-cycle",
                body="mint proof attached off-wire",
            )
            print(f"published mail packet={published.packet_id} relays={published.details.get('relays')}")
            if not published.ok:
                raise CheckFailure("mail publish failed")
            inbox = node_b.fetch_mail()
            if len(inbox) != 1:
                raise CheckFailure(f"expected 1 mail, got {len(inbox)}")
            message = inbox[0]
            print(f"bob opened subject={message.subject!r} body={message.body!r}")
            if message.body != "mint proof attached off-wire":
                raise CheckFailure("decrypted body mismatch")
            if message.sender_hash != node_a.identity.identity_hash:
                raise CheckFailure("sender hash mismatch")
            raw = node_b.relay.query(recipient_hash=node_b.identity.identity_hash, kind="MAIL_SEALED")
            sealed = raw[0]["content"]["sealed"]
            try:
                stranger.open_sealed(sealed)
                raise CheckFailure("stranger opened mail addressed to Bob")
            except ValueError as exc:
                print(f"stranger correctly failed: {exc}")
            receipt = node_b.ack_mail(sender=node_a.identity, ref_packet_id=message.packet_id)
            print(f"receipt packet={receipt.packet_id}")
            details["packet_id"] = published.packet_id
            details["relays"] = published.details.get("relays")
            details["alice_address"] = node_a.identity.mesh_address
        finally:
            _close_pair(node_a, node_b, fw_a, fw_b)


def check_legacy_ip_rejected(details: dict[str, object]) -> None:
    """Overlay refuses destination_ip even before a packet is signed."""
    try:
        reject_legacy_routing({"destination_ip": "203.0.113.9", "note": "legacy"})
        raise CheckFailure("destination_ip was accepted")
    except EmailSocialBlocked as exc:
        print(f"routing rejected: {exc}")
    try:
        reject_legacy_routing({"address": "198.51.100.10:443"})
        raise CheckFailure("IPv4 address field was accepted")
    except EmailSocialBlocked as exc:
        print(f"address rejected: {exc}")
    details["rejected"] = True


def check_relay_blocks_unsigned_and_routing(details: dict[str, object]) -> None:
    """Relays drop unsigned packets and next_hop routing artifacts."""
    with tempfile.TemporaryDirectory(prefix="mail_relay_") as tmpdir:
        identity = SovereignIdentity("RelayOp")
        peer = SovereignIdentity("Peer")
        store = PANPersistenceStore(base_path=Path(tmpdir) / "pan")
        firewall = SovereignFirewall(Path(tmpdir) / "fw.sqlite")
        node = EmailSocialNode(identity, store, firewall)
        try:
            communicator = SovereignCommunicator(identity)
            unsigned = communicator.create_packet(
                "MAIL_SEALED",
                {
                    "recipient": peer.identity_hash,
                    "sealed": seal_plaintext(b"hello", peer.get_public_key_pem()),
                },
            )
            unsigned.signature = b"\x00" * 64
            try:
                node.relay.accept(
                    unsigned,
                    author_public_key_pem=identity.get_public_key_pem(),
                    firewall=firewall,
                )
                raise CheckFailure("relay accepted a forged signature")
            except EmailSocialRelayError as exc:
                print(f"forged signature rejected: {exc}")
            routed = communicator.create_packet(
                "SOCIAL_BROADCAST",
                {"text": "hello", "next_hop": "carrier-gateway"},
                metadata={
                    "author_public_key_pem": identity.get_public_key_pem().decode("utf-8"),
                    "mesh_address": identity.mesh_address,
                },
            )
            try:
                node.relay.accept(
                    routed,
                    author_public_key_pem=identity.get_public_key_pem(),
                    firewall=firewall,
                )
                raise CheckFailure("relay accepted next_hop routing")
            except EmailSocialBlocked as exc:
                print(f"next_hop rejected: {exc}")
            details["forged_rejected"] = True
            details["routing_rejected"] = True
        finally:
            firewall.close()
            store.close()


def check_social_and_knock(details: dict[str, object]) -> None:
    """Public social posts replicate; knocks expire without carrying IP."""
    with tempfile.TemporaryDirectory(prefix="mail_social_") as tmpdir:
        node_a, node_b, fw_a, fw_b = _pair(tmpdir, "SocialAnn", "SocialBea")
        try:
            post = node_a.broadcast_social("citizen assembly at dusk", feed="agora")
            print(f"social packet={post.packet_id}")
            feed = node_b.fetch_social(feed="agora")
            if len(feed) != 1:
                raise CheckFailure(f"expected 1 social post, got {len(feed)}")
            text = feed[0]["content"]["text"]
            print(f"bea saw text={text!r}")
            if text != "citizen assembly at dusk":
                raise CheckFailure("social text mismatch")
            knock = node_a.knock(
                recipient_hash=node_b.identity.identity_hash,
                tunnel_id="tunnel-alpha",
                ttl_seconds=1,
            )
            live = node_b.fetch_knocks()
            print(f"live knocks={len(live)} expires={knock.details.get('expires_at')}")
            if len(live) != 1:
                raise CheckFailure("knock was not visible before expiry")
            time.sleep(1.2)
            expired_view = node_b.fetch_knocks()
            dropped = node_a.relay.drop_expired_knocks() + node_b.relay.drop_expired_knocks()
            print(f"after ttl knocks={len(expired_view)} dropped={dropped}")
            if expired_view:
                raise CheckFailure("expired knock was still visible")
            if dropped < 1:
                raise CheckFailure("relays did not drop expired knocks")
            details["social_id"] = post.packet_id
            details["knocks_dropped"] = dropped
        finally:
            _close_pair(node_a, node_b, fw_a, fw_b)


def check_restart_hydrates_relay(details: dict[str, object]) -> None:
    """Mail stored on a relay survives process restart on the same sqlite."""
    with tempfile.TemporaryDirectory(prefix="mail_restart_") as tmpdir:
        ident_a = SovereignIdentity("RestartAnn")
        ident_b = SovereignIdentity("RestartBea")
        pem_b = ident_b.serialize_private_key()
        store_a = PANPersistenceStore(base_path=Path(tmpdir) / "a")
        store_b = PANPersistenceStore(base_path=Path(tmpdir) / "b")
        fw_a = SovereignFirewall(Path(tmpdir) / "fw_a.sqlite")
        fw_b = SovereignFirewall(Path(tmpdir) / "fw_b.sqlite")
        node_a = EmailSocialNode(ident_a, store_a, fw_a)
        node_b = EmailSocialNode(ident_b, store_b, fw_b)
        node_a.add_peer_relay(node_b.relay)
        try:
            node_a.send_mail(recipient=ident_b, body="persist-me")
            details["before"] = len(node_b.fetch_mail())
        finally:
            fw_a.close()
            fw_b.close()
            store_a.close()
            store_b.close()

        store_b2 = PANPersistenceStore(base_path=Path(tmpdir) / "b")
        fw_b2 = SovereignFirewall(Path(tmpdir) / "fw_b.sqlite")
        restored = SovereignIdentity("RestartBea", private_key_pem=pem_b)
        node_b2 = EmailSocialNode(restored, store_b2, fw_b2)
        try:
            inbox = node_b2.fetch_mail()
            print(f"reopened inbox={len(inbox)} body={inbox[0].body if inbox else None}")
            if len(inbox) != 1 or inbox[0].body != "persist-me":
                raise CheckFailure("relay did not hydrate sealed mail")
            details["after"] = len(inbox)
        finally:
            fw_b2.close()
            store_b2.close()


CHECKS = (
    ("sealed_mail_across_relays", check_sealed_mail_across_relays),
    ("legacy_ip_rejected", check_legacy_ip_rejected),
    ("relay_blocks_unsigned_and_routing", check_relay_blocks_unsigned_and_routing),
    ("social_and_knock", check_social_and_knock),
    ("restart_hydrates_relay", check_restart_hydrates_relay),
)


def run() -> dict[str, object]:
    """Execute every email/social check and return a gate-shaped payload."""
    started = time.time()
    checks: list[dict[str, object]] = []
    passed_count = 0
    failed_count = 0
    for name, fn in CHECKS:
        _print_banner(f"CHECK: {name}")
        detail: dict[str, object] = {}
        try:
            fn(detail)
            print(f"PASS {name}")
            checks.append({"name": name, "status": "pass", "detail": detail})
            passed_count += 1
        except CheckFailure as exc:
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
            checks.append({"name": name, "status": "fail", "error": str(exc), "detail": detail})
            failed_count += 1
        except (
            EmailSocialError,
            EmailSocialBlocked,
            EmailSocialCryptoError,
            EmailSocialRelayError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            sqlite3.Error,
        ) as exc:
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                    "detail": detail,
                }
            )
            failed_count += 1
    elapsed = time.time() - started
    passed = failed_count == 0
    payload: dict[str, object] = {
        "name": "email_social",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} email_social checks failed"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    artifacts = write_artifacts(payload, timestamp, "invoked via run()\n")
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def write_artifacts(payload: dict[str, object], timestamp: str, log_text: str) -> dict[str, Path]:
    """Write Code Forge JSON, Markdown, and log artifacts for this run."""
    run_dir = CURRENT_DIR / "runs" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "result.json"
    md_path = run_dir / "result.md"
    log_path = run_dir / "result.log"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    log_path.write_text(log_text, encoding="utf-8")
    lines = [
        f"# Email/social overlay run {timestamp}",
        "",
        f"I ran `python test/email_social/test_email_social.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required identity-hash addressing, hybrid sealed mail, blind dual relays,",
        "firewall inspection, IP rejection, and sqlite hydrate after reopen.",
        "",
        "## Checks",
        "",
    ]
    for item in payload.get("checks", []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('name')}`: {item.get('status')}")
        if item.get("error"):
            lines.append(f"  - error: `{item.get('error')}`")
    lines.extend(["", "## Artifacts", "", f"- `{json_path}`", f"- `{md_path}`", f"- `{log_path}`", ""])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path, "log": log_path, "run_dir": run_dir}


def main() -> int:
    """Run checks, persist artifacts, print a gate-shaped summary."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        print(f"email_social consumer start {timestamp}")
        payload = run()
        print(f"email_social consumer status={payload.get('status')}")
    log_text = buffer.getvalue()
    sys.stdout.write(log_text)
    artifacts = write_artifacts(payload, timestamp, log_text)
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"artifacts json={artifacts['json']}")
    print(f"artifacts md={artifacts['md']}")
    print(f"artifacts log={artifacts['log']}")
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
