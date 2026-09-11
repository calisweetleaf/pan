"""Direct consumer for the planetary immune system.

Real tempdir USMS + SQLite firewall ledger + two PAN DHT nodes.
No mocks. Prints a run report and writes JSON/MD/LOG artifacts.
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
from typing import Callable

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import SovereignCommunicator, SovereignIdentity, UnifiedDataPacket
from memory.unified_memory_system import (
    LinkageTypeEnum,
    MemoryAccessError,
    SovereignIdentityError,
    UnifiedMemoryError,
)
from security.planetary_immune_system import (
    BulletinVerificationError,
    ImmuneSystemError,
    PlanetaryImmuneSystem,
)
from security.sovereign_firewall import (
    FirewallError,
    InspectionAction,
    InspectionLane,
    SovereignFirewall,
    THREAT_BULLETIN_KIND,
)


CheckFn = Callable[[dict[str, object]], None]


class CheckFailure(Exception):
    """A named immune-system check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _make_packet(
    identity: SovereignIdentity,
    kind: str,
    content: dict[str, object],
) -> UnifiedDataPacket:
    """Sign a packet with a real PAN identity."""
    communicator = SovereignCommunicator(identity)
    return communicator.create_packet(kind, content)


def check_firewall_blocks_telemetry(details: dict[str, object]) -> None:
    """EGRESS_LEGACY drops tracker payloads and ledgers the drop."""
    with tempfile.TemporaryDirectory(prefix="fw_telemetry_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "METRICS_UPLOAD",
                {"message": "export user_activity to google-analytics"},
            )
            verdict = firewall.inspect_packet(packet, lane=InspectionLane.EGRESS_LEGACY)
            print(f"telemetry action={verdict.action.value} reason={verdict.reason}")
            if not verdict.blocked:
                raise CheckFailure("telemetry packet was allowed")
            if verdict.reason not in {"telemetry_dictionary", "telemetry_regex"}:
                raise CheckFailure(f"unexpected telemetry reason: {verdict.reason}")
            events = firewall.ledger_events(limit=5)
            if not events:
                raise CheckFailure("firewall ledger is empty after a block")
            details["telemetry_reason"] = verdict.reason
            details["telemetry_ledger_rows"] = len(events)
        finally:
            firewall.close()


def check_firewall_allows_civic_chat(details: dict[str, object]) -> None:
    """A civic chat packet is allowed on EGRESS_LEGACY."""
    with tempfile.TemporaryDirectory(prefix="fw_chat_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "CHAT_MESSAGE",
                {"message": "hello from the sovereign mesh"},
            )
            verdict = firewall.inspect_packet(packet)
            print(f"civic chat action={verdict.action.value}")
            if verdict.blocked:
                raise CheckFailure(f"civic chat blocked: {verdict.reason}")
            details["civic_chat_allowed"] = True
        finally:
            firewall.close()


def check_inspect_content_compresses_secrets(details: dict[str, object]) -> None:
    """Pre-packet inspection envelopes secrets instead of shipping plaintext."""
    with tempfile.TemporaryDirectory(prefix="fw_compress_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        try:
            verdict = firewall.inspect_content(
                {"password": "correct-horse-battery", "note": "citizen vault"},
                lane=InspectionLane.EGRESS_LEGACY,
            )
            print(f"secret preflight action={verdict.action.value}")
            if verdict.action is not InspectionAction.COMPRESS:
                raise CheckFailure(f"expected COMPRESS, got {verdict.action.value}")
            envelope = verdict.sanitized_content
            if not isinstance(envelope, dict) or envelope.get("lacka_envelope") is not True:
                raise CheckFailure("compress path did not return a lacka envelope")
            if "correct-horse-battery" in json.dumps(envelope):
                raise CheckFailure("plaintext secret survived compression")
            details["compressed_bytes"] = envelope.get("compressed_bytes")
            details["original_bytes"] = envelope.get("original_bytes")
        finally:
            firewall.close()


def check_signed_secret_packet_is_blocked(details: dict[str, object]) -> None:
    """inspect_packet never mutates a signed packet; secrets fail closed."""
    with tempfile.TemporaryDirectory(prefix="fw_signed_secret_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "DATA_TRANSFER",
                {"password": "should-not-cross-the-border"},
            )
            original = dict(packet.content)
            verdict = firewall.inspect_packet(packet)
            print(f"signed secret action={verdict.action.value} reason={verdict.reason}")
            if not verdict.blocked:
                raise CheckFailure("signed secret packet was allowed")
            if packet.content != original:
                raise CheckFailure("inspect_packet mutated a signed packet")
            details["signed_secret_blocked"] = True
        finally:
            firewall.close()


def check_identity_blocklist(details: dict[str, object]) -> None:
    """Blocked identities cannot send packets."""
    with tempfile.TemporaryDirectory(prefix="fw_block_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        hostile = SovereignIdentity("HostileNode")
        try:
            firewall.block_identity(hostile.identity_hash, reason="test_block")
            packet = _make_packet(hostile, "CHAT_MESSAGE", {"message": "hello"})
            verdict = firewall.inspect_packet(packet)
            print(f"blocklist action={verdict.action.value}")
            if verdict.reason != "identity_blocklist":
                raise CheckFailure(f"expected identity_blocklist, got {verdict.reason}")
            details["blocked_identity"] = hostile.identity_hash[:12]
        finally:
            firewall.close()


def check_memory_survives_restart(details: dict[str, object]) -> None:
    """USMS threat events survive process restart via the same runtime root."""
    with tempfile.TemporaryDirectory(prefix="immune_restart_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        first = None
        second = None
        try:
            first = PlanetaryImmuneSystem(root, node_name="immune-alpha")
            record = first.share_intelligence(
                {
                    "threat_type": "polymorphic_loader_v3",
                    "confidence": 0.91,
                    "actionable": True,
                    "vector": "network",
                    "summary": "novel loader dropped a packed beacon",
                },
                source="defensive_sovereignty",
            )
            print(
                f"first share intel_id={record.intel_id} event={record.event_node_id[:12]} "
                f"belief={record.belief_node_id[:12] if record.belief_node_id else None} "
                f"dht={record.bulletin_dht_key}"
            )
            if record.belief_node_id is None:
                raise CheckFailure("high-confidence share did not create a BELIEF node")
            if record.bulletin_dht_key is None:
                raise CheckFailure("high-confidence share did not broadcast a bulletin")
            details["intel_id"] = record.intel_id
            details["event_node_id"] = record.event_node_id
            details["belief_node_id"] = record.belief_node_id
            details["bulletin_dht_key"] = record.bulletin_dht_key
            first.close()
            first = None
            second = PlanetaryImmuneSystem(root, node_name="immune-alpha")
            hits = second.get_relevant_intelligence(
                {"threat_type": "polymorphic_loader_v3"}
            )
            print(f"restart search hits={len(hits)}")
            if not hits:
                raise CheckFailure("USMS amnesia after restart")
            recovered_ids = {str(item.get("intel_id")) for item in hits}
            if details["intel_id"] not in recovered_ids:
                raise CheckFailure("restart search missed the original intel_id")
            node = second.memory.retrieve_memory_node(
                str(details["event_node_id"]),
                requester=second.memory_identity,
            )
            if node is None:
                raise CheckFailure("event node missing after restart")
            details["restart_hits"] = len(hits)
        finally:
            if first is not None:
                first.close()
            if second is not None:
                second.close()


def check_peer_ingests_bulletin(details: dict[str, object]) -> None:
    """A second node remembers a high-confidence bulletin pulled from the first DHT."""
    with tempfile.TemporaryDirectory(prefix="immune_mesh_", ignore_cleanup_errors=True) as tmpdir:
        alpha_root = Path(tmpdir) / "alpha"
        bravo_root = Path(tmpdir) / "bravo"
        alpha = None
        bravo = None
        try:
            alpha = PlanetaryImmuneSystem(alpha_root, node_name="immune-alpha")
            bravo = PlanetaryImmuneSystem(bravo_root, node_name="immune-bravo")
            record = alpha.share_intelligence(
                {
                    "threat_type": "zero_day_loader",
                    "confidence": 0.88,
                    "actionable": True,
                    "summary": "zero-day loader observed on the civic bus",
                },
                source="defensive_sovereignty",
            )
            if record.bulletin_dht_key is None:
                raise CheckFailure("alpha did not broadcast")
            packet_dict = alpha.lookup_bulletin(record.bulletin_dht_key)
            if packet_dict is None:
                raise CheckFailure("alpha DHT lookup missed the bulletin")
            ingested = bravo.ingest_bulletin(packet_dict)
            print(
                f"bravo ingested intel_id={ingested.intel_id} "
                f"event={ingested.event_node_id[:12]}"
            )
            hits = bravo.get_relevant_intelligence({"threat_type": "zero_day_loader"})
            if not hits:
                raise CheckFailure("bravo semantic search missed ingested bulletin")
            details["peer_ingested_intel_id"] = ingested.intel_id
            details["peer_hits"] = len(hits)
            details["packet_kind"] = packet_dict.get("kind")
            if details["packet_kind"] != THREAT_BULLETIN_KIND:
                raise CheckFailure(f"unexpected bulletin kind {details['packet_kind']}")
        finally:
            if alpha is not None:
                alpha.close()
            if bravo is not None:
                bravo.close()


def check_contradiction_and_campaign_entangle(details: dict[str, object]) -> None:
    """Failed countermeasures write CONTRADICTION; three campaign vectors entangle."""
    with tempfile.TemporaryDirectory(prefix="immune_campaign_", ignore_cleanup_errors=True) as tmpdir:
        immune = None
        try:
            immune = PlanetaryImmuneSystem(Path(tmpdir), node_name="immune-campaign")
            last = None
            for vector in ("network", "filesystem", "memory"):
                last = immune.share_intelligence(
                    {
                        "threat_type": "coordinated_campaign",
                        "campaign_id": "campaign-omega",
                        "vector": vector,
                        "confidence": 0.8,
                        "actionable": True,
                        "summary": f"campaign omega hit {vector}",
                    },
                    source="defensive_sovereignty",
                )
                print(f"campaign vector={vector} event={last.event_node_id[:12]}")
            if last is None or last.belief_node_id is None:
                raise CheckFailure("campaign share failed to produce a belief")
            if last.entanglement_id is None:
                raise CheckFailure("third campaign vector did not quantum-entangle")
            failure = immune.record_countermeasure_failure(
                last.belief_node_id,
                "countermeasure failed against campaign omega",
                {"reason": "peer already rotated implants"},
            )
            contradiction_targets = failure.linkage_manifest.get(
                LinkageTypeEnum.CONTRADICTION,
                [],
            )
            print(
                f"contradiction node={failure.node_id[:12]} "
                f"targets={contradiction_targets}"
            )
            if last.belief_node_id not in contradiction_targets:
                raise CheckFailure("failure EVENT is not CONTRADICTION-linked to the belief")
            details["entanglement_id"] = last.entanglement_id
            details["contradiction_node_id"] = failure.node_id
            details["contradictions"] = immune.metrics["contradictions"]
        finally:
            if immune is not None:
                immune.close()


def check_legacy_ip_routing_blocked(details: dict[str, object]) -> None:
    """Legacy ISP routing artifacts never leave through EGRESS_LEGACY."""
    with tempfile.TemporaryDirectory(prefix="fw_route_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "ROUTE_HINT",
                {"next_hop": "isp-gateway", "message": "please route via carrier"},
            )
            verdict = firewall.inspect_packet(packet, lane=InspectionLane.EGRESS_LEGACY)
            print(f"routing action={verdict.action.value} reason={verdict.reason}")
            if verdict.reason != "legacy_routing_artifact":
                raise CheckFailure(f"expected legacy_routing_artifact, got {verdict.reason}")
            details["routing_blocked"] = True
        finally:
            firewall.close()


CHECKS: tuple[tuple[str, CheckFn], ...] = (
    ("firewall_blocks_telemetry", check_firewall_blocks_telemetry),
    ("firewall_allows_civic_chat", check_firewall_allows_civic_chat),
    ("inspect_content_compresses_secrets", check_inspect_content_compresses_secrets),
    ("signed_secret_packet_is_blocked", check_signed_secret_packet_is_blocked),
    ("identity_blocklist", check_identity_blocklist),
    ("legacy_ip_routing_blocked", check_legacy_ip_routing_blocked),
    ("memory_survives_restart", check_memory_survives_restart),
    ("peer_ingests_bulletin", check_peer_ingests_bulletin),
    ("contradiction_and_campaign_entangle", check_contradiction_and_campaign_entangle),
)


def run() -> dict[str, object]:
    """Execute every immune-system check and return a gate-shaped payload."""
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
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "error": str(exc),
                    "detail": detail,
                }
            )
            failed_count += 1
        except (
            ImmuneSystemError,
            BulletinVerificationError,
            FirewallError,
            UnifiedMemoryError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            MemoryAccessError,
            SovereignIdentityError,
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
        "name": "planetary_immune_system",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} immune checks failed"
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
        f"# Planetary immune system run {timestamp}",
        "",
        f"I ran `python test/immune/test_planetary_immune_system.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required a real USMS sqlite file, a real firewall ledger, and two PAN DHT nodes.",
        "I required the demo firewall to be gone. I required high-confidence beliefs to",
        "become `THREAT_MEMORY_BULLETIN` packets that a peer can ingest after restart.",
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
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `{json_path}`",
            f"- `{md_path}`",
            f"- `{log_path}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path, "log": log_path, "run_dir": run_dir}


def main() -> int:
    """Run checks, persist artifacts, print a gate-shaped summary."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        print(f"immune consumer start {timestamp}")
        payload = run()
        print(f"immune consumer status={payload.get('status')}")
    log_text = buffer.getvalue()
    sys.stdout.write(log_text)
    artifacts = write_artifacts(payload, timestamp, log_text)
    print(f"artifacts json={artifacts['json']}")
    print(f"artifacts md={artifacts['md']}")
    print(f"artifacts log={artifacts['log']}")
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
