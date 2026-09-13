"""Direct consumer for the planetary highway packet fabric.

Three in-process identity-hash hops. Real tempdir USMS + SQLite relays.
No mocks. No public internet. Prints a run report and writes JSON/MD/LOG.
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

from PAN_SDK import DHTNode, PANPersistenceStore, SovereignCommunicator, SovereignIdentity
from PAN_SDK.email_social import seal_plaintext
from PAN_SDK.PAN_SDK import UnifiedDataPacket, canonical
from memory.unified_memory_system import (
    NodeKindEnum,
    SovereignIdentity as MemorySovereignIdentity,
    UnifiedMemorySystem,
)
from security.planetary_highway import (
    HIGHWAY_HOP,
    HighwayCargoError,
    HighwayError,
    HighwayFirewallError,
    HighwayNotBoundError,
    HighwayRouteError,
    PlanetaryHighway,
)
from security.sovereign_firewall import SovereignFirewall


CheckFn = Callable[[dict[str, object]], None]

BANNED_SOURCE = (
    "pickle",
    "Fernet",
    "255.255.255.255",
    "mock_result",
    "consciousness_providers",
    "numpy",
    "asyncio.start_server",
    "SOCK_DGRAM",
    "get_global_network",
    "PlanetaryARFSNetwork",
)

CARGO_CLAIM = "citizen assembly itinerary fragment for the destination only"


class CheckFailure(Exception):
    """A named highway check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _memory_identity(name: str) -> MemorySovereignIdentity:
    return MemorySovereignIdentity(
        agent_name=name,
        agent_id="",
        public_key="",
        creation_timestamp=0.0,
    )


def _open_highway(root: Path, name: str) -> PlanetaryHighway:
    """Open one highway citizen with its own USMS, firewall, and store."""
    pan = SovereignIdentity(name)
    memory_id = _memory_identity(f"{name}-memory")
    usms_root = root / "usms"
    usms_root.mkdir(parents=True, exist_ok=True)
    memory = UnifiedMemorySystem(
        db_path=str(usms_root / "unified_sovereign_memory.db"),
        config={"runtime_root": str(usms_root), "console_logging": False},
        enable_quantum_features=True,
    )
    memory.register_sovereign(memory_id)
    store = PANPersistenceStore(base_path=root / "pan")
    firewall = SovereignFirewall(root / "fw.sqlite")
    return PlanetaryHighway(
        pan_identity=pan,
        memory=memory,
        memory_identity=memory_id,
        firewall=firewall,
        persistence=store,
    )


def _close_highway(highway: PlanetaryHighway) -> None:
    """Close sqlite handles this test opened. Highway does not own them."""
    highway.memory.shutdown()
    highway.firewall.close()
    highway.persistence.close()


def _pair_three(
    tmpdir: str,
) -> tuple[PlanetaryHighway, PlanetaryHighway, PlanetaryHighway]:
    """Open origin, hop, dest and cross-register peer relays."""
    root = Path(tmpdir)
    origin = _open_highway(root / "origin", "HwyOrigin")
    hop = _open_highway(root / "hop", "HwyHop")
    dest = _open_highway(root / "dest", "HwyDest")
    origin.add_peer_relay(hop.relay)
    origin.add_peer_relay(dest.relay)
    hop.add_peer_relay(origin.relay)
    hop.add_peer_relay(dest.relay)
    dest.add_peer_relay(origin.relay)
    dest.add_peer_relay(hop.relay)
    return origin, hop, dest


def _close_three(
    origin: PlanetaryHighway,
    hop: PlanetaryHighway,
    dest: PlanetaryHighway,
) -> None:
    _close_highway(origin)
    _close_highway(hop)
    _close_highway(dest)


def _seed_node(highway: PlanetaryHighway, claim: str) -> str:
    node = highway.memory.create_memory_node(
        author=highway.memory_identity,
        kind=NodeKindEnum.EVENT,
        content={"claim": claim, "summary": claim},
        semantic_context="highway_cargo",
    )
    return node.node_id


def check_source_has_no_legacy_mesh(details: dict[str, object]) -> None:
    """The highway owner must not contain the rejected ARFS civic wire."""
    source = (ROOT_DIR / "security" / "planetary_highway.py").read_text(encoding="utf-8")
    found = [token for token in BANNED_SOURCE if token in source]
    print(f"banned tokens found={found}")
    if found:
        raise CheckFailure(f"highway source still contains {found}")
    details["banned_absent"] = True
    details["source_chars"] = len(source)


def check_requires_explicit_firewall(details: dict[str, object]) -> None:
    """Firewall is required. Highway never invents one on DHTNode."""
    with tempfile.TemporaryDirectory(prefix="hwy_fw_", ignore_cleanup_errors=True) as tmpdir:
        pan = SovereignIdentity("NoFirewall")
        memory_id = _memory_identity("NoFirewall-memory")
        root = Path(tmpdir)
        memory = UnifiedMemorySystem(
            db_path=str(root / "usms.db"),
            config={"runtime_root": str(root), "console_logging": False},
        )
        memory.register_sovereign(memory_id)
        store = PANPersistenceStore(base_path=root / "pan")
        try:
            try:
                PlanetaryHighway(
                    pan_identity=pan,
                    memory=memory,
                    memory_identity=memory_id,
                    firewall=None,  # type: ignore[arg-type]
                    persistence=store,
                )
            except HighwayNotBoundError as exc:
                print(f"unbound firewall refused: {exc}")
                details["refused"] = True
            else:
                raise CheckFailure("highway constructed without a firewall")
        finally:
            memory.shutdown()
            store.close()


def check_direct_travel_sealed_cargo(details: dict[str, object]) -> None:
    """Direct hop: dest opens cargo; a stranger cannot."""
    with tempfile.TemporaryDirectory(prefix="hwy_direct_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        stranger = SovereignIdentity("Stranger")
        try:
            node_id = _seed_node(origin, CARGO_CLAIM)
            ticket = origin.embark(dest.pan_identity, [node_id], via=())
            print(f"embark travel={ticket.travel_id} packet={ticket.packet_id}")
            arrived = dest.transit()
            if len(arrived) != 1 or arrived[0].reason != "arrived":
                raise CheckFailure(f"expected one arrive, got {arrived}")
            raw = dest.relay.query(
                recipient_hash=dest.pan_identity.identity_hash, kind=HIGHWAY_HOP
            )
            if not raw:
                raise CheckFailure("destination relay missing HIGHWAY_HOP")
            sealed = raw[0]["content"]["sealed_cargo"]
            dest.pan_identity.open_sealed(sealed)
            try:
                stranger.open_sealed(sealed)
                raise CheckFailure("stranger opened cargo sealed to dest")
            except ValueError as exc:
                print(f"stranger correctly failed: {exc}")
            event = dest.memory.retrieve_memory_node(
                str(arrived[0].details["event_node_id"]),
                requester=dest.memory_identity,
            )
            if event is None:
                raise CheckFailure("destination did not write a local EVENT")
            if event.content.get("origin_node_id") != node_id:
                raise CheckFailure("local EVENT did not cite origin_node_id")
            details["travel_id"] = ticket.travel_id
            details["arrived"] = True
        finally:
            _close_three(origin, hop, dest)


def check_multi_hop_three_nodes(details: dict[str, object]) -> None:
    """Hop forwards sealed cargo and never sees plaintext cognition."""
    with tempfile.TemporaryDirectory(prefix="hwy_multi_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        try:
            node_id = _seed_node(origin, CARGO_CLAIM)
            ticket = origin.embark(
                dest.pan_identity,
                [node_id],
                via=(hop.pan_identity.identity_hash,),
            )
            print(f"multi embark next={ticket.next_identity_hash[:12]}")
            forwarded = hop.transit()
            if not forwarded or forwarded[0].reason != "forwarded":
                raise CheckFailure(f"hop did not forward: {forwarded}")
            hits = hop.memory.search_nodes_by_content(
                CARGO_CLAIM, requester=hop.memory_identity
            )
            leaked = [
                node.node_id
                for node in hits
                if CARGO_CLAIM in json.dumps(node.content)
            ]
            print(f"hop USMS hits={len(hits)} leaked={len(leaked)}")
            if leaked:
                raise CheckFailure("hop USMS contains cargo plaintext")
            hop_events = hop.relay.query(
                recipient_hash=hop.pan_identity.identity_hash, kind=HIGHWAY_HOP
            )
            if not hop_events:
                raise CheckFailure("hop relay missing first HIGHWAY_HOP")
            sealed = hop_events[0]["content"]["sealed_cargo"]
            try:
                hop.pan_identity.open_sealed(sealed)
                raise CheckFailure("hop opened cargo sealed to dest")
            except ValueError as exc:
                print(f"hop correctly cannot open: {exc}")
            arrived = dest.transit()
            if not arrived or arrived[0].reason != "arrived":
                raise CheckFailure(f"dest did not arrive: {arrived}")
            dest_event = dest.memory.retrieve_memory_node(
                str(arrived[0].details["event_node_id"]),
                requester=dest.memory_identity,
            )
            if dest_event is None or CARGO_CLAIM not in json.dumps(dest_event.content):
                raise CheckFailure("destination local EVENT missing cargo claim")
            details["forwarded"] = True
            details["hop_plaintext"] = False
        finally:
            _close_three(origin, hop, dest)


def check_firewall_blocks_telemetry_on_hop(details: dict[str, object]) -> None:
    """A hop envelope that names a tracker is dropped at the border."""
    with tempfile.TemporaryDirectory(prefix="hwy_telem_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        try:
            sealed = seal_plaintext(
                b'{"claim":"no"}', dest.pan_identity.get_public_key_pem()
            )
            try:
                origin._inspect_sign_publish(
                    HIGHWAY_HOP,
                    {
                        "recipient": hop.pan_identity.identity_hash,
                        "next_identity_hash": hop.pan_identity.identity_hash,
                        "destination_identity_hash": dest.pan_identity.identity_hash,
                        "message": "export user_activity to google-analytics",
                        "sealed_cargo": sealed,
                    },
                )
            except HighwayFirewallError as exc:
                print(f"telemetry hop blocked: {exc}")
                details["blocked"] = True
            else:
                raise CheckFailure("telemetry hop was published")
        finally:
            _close_three(origin, hop, dest)


def check_legacy_routing_key_rejected(details: dict[str, object]) -> None:
    """next_hop never becomes a highway envelope key."""
    with tempfile.TemporaryDirectory(prefix="hwy_route_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        try:
            routed_node = origin.memory.create_memory_node(
                author=origin.memory_identity,
                kind=NodeKindEnum.EVENT,
                content={"claim": "routed cargo", "next_hop": "isp-gateway"},
                semantic_context="highway_cargo",
            )
            try:
                origin.embark(dest.pan_identity, [routed_node.node_id], via=())
            except (HighwayRouteError, HighwayCargoError) as exc:
                print(f"legacy routing refused: {exc}")
                details["rejected"] = True
            else:
                raise CheckFailure("embark accepted next_hop cargo")
            try:
                origin._inspect_sign_publish(
                    HIGHWAY_HOP,
                    {
                        "recipient": dest.pan_identity.identity_hash,
                        "next_identity_hash": dest.pan_identity.identity_hash,
                        "destination_identity_hash": dest.pan_identity.identity_hash,
                        "next_hop": "carrier-gateway",
                        "sealed_cargo": seal_plaintext(
                            b'{"ok":true}', dest.pan_identity.get_public_key_pem()
                        ),
                    },
                )
            except HighwayRouteError as exc:
                print(f"envelope next_hop refused: {exc}")
                details["envelope_rejected"] = True
            else:
                raise CheckFailure("inspect/sign accepted next_hop")
        finally:
            _close_three(origin, hop, dest)


def check_identity_blocklist_stops_travel(details: dict[str, object]) -> None:
    """A blocked origin cannot publish a hop."""
    with tempfile.TemporaryDirectory(prefix="hwy_block_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        try:
            node_id = _seed_node(origin, CARGO_CLAIM)
            origin.firewall.block_identity(
                origin.pan_identity.identity_hash, reason="test_block"
            )
            try:
                origin.embark(dest.pan_identity, [node_id], via=())
            except HighwayFirewallError as exc:
                print(f"blocklist stopped travel: {exc}")
                details["blocked"] = True
            else:
                raise CheckFailure("blocked origin still embarked")
        finally:
            _close_three(origin, hop, dest)


def check_bad_usms_signature_fails_loud(details: dict[str, object]) -> None:
    """Tampered Ed25519 cargo fails at destination arrive."""
    with tempfile.TemporaryDirectory(prefix="hwy_badsig_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        try:
            node_id = _seed_node(origin, CARGO_CLAIM)
            origin.embark(dest.pan_identity, [node_id], via=())
            raw = dest.relay.query(
                recipient_hash=dest.pan_identity.identity_hash, kind=HIGHWAY_HOP
            )
            if not raw:
                raise CheckFailure("missing hop for tamper test")
            packet = UnifiedDataPacket.from_dict(dict(raw[0]))
            opened = dest.pan_identity.open_sealed(packet.content["sealed_cargo"])
            cargo = json.loads(opened.decode("utf-8"))
            cargo["usms_signature"] = "ab" * 64
            tampered = seal_plaintext(
                canonical(cargo).encode("utf-8"),
                dest.pan_identity.get_public_key_pem(),
            )
            communicator = SovereignCommunicator(origin.pan_identity)
            forged = communicator.create_packet(
                HIGHWAY_HOP,
                {
                    "recipient": dest.pan_identity.identity_hash,
                    "next_identity_hash": dest.pan_identity.identity_hash,
                    "destination_identity_hash": dest.pan_identity.identity_hash,
                    "origin_identity_hash": origin.pan_identity.identity_hash,
                    "travel_id": str(packet.content.get("travel_id") or "tamper"),
                    "hop_index": 0,
                    "itinerary": [dest.pan_identity.identity_hash],
                    "sealed_cargo": tampered,
                },
                metadata={
                    "author_public_key_pem": origin.pan_identity.get_public_key_pem().decode(
                        "utf-8"
                    ),
                    "mesh_address": origin.pan_identity.mesh_address,
                },
            )
            try:
                dest.arrive(forged)
            except HighwayCargoError as exc:
                print(f"bad USMS signature refused: {exc}")
                details["refused"] = True
            else:
                raise CheckFailure("tampered USMS cargo was ingested")
        finally:
            _close_three(origin, hop, dest)


def check_cargo_survives_restart(details: dict[str, object]) -> None:
    """Destination receipts and local USMS nodes survive reopen."""
    with tempfile.TemporaryDirectory(prefix="hwy_restart_", ignore_cleanup_errors=True) as tmpdir:
        origin, hop, dest = _pair_three(tmpdir)
        dest_root = Path(tmpdir) / "dest"
        try:
            node_id = _seed_node(origin, CARGO_CLAIM)
            ticket = origin.embark(dest.pan_identity, [node_id], via=())
            arrived = dest.transit()
            if not arrived:
                raise CheckFailure("arrive missing before restart")
            event_id = str(arrived[0].details["event_node_id"])
            travel_id = ticket.travel_id
            pan = dest.pan_identity
            memory_id = dest.memory_identity
            dest.memory.shutdown()
            dest.firewall.close()
            dest.persistence.close()
            dest = None  # type: ignore[assignment]
            reopened_memory = UnifiedMemorySystem(
                db_path=str(dest_root / "usms" / "unified_sovereign_memory.db"),
                config={"runtime_root": str(dest_root / "usms"), "console_logging": False},
            )
            reopened_memory.register_sovereign(memory_id)
            store = PANPersistenceStore(base_path=dest_root / "pan")
            firewall = SovereignFirewall(dest_root / "fw.sqlite")
            reopened = PlanetaryHighway(
                pan_identity=pan,
                memory=reopened_memory,
                memory_identity=memory_id,
                firewall=firewall,
                persistence=store,
            )
            try:
                located = reopened.locate(travel_id)
                print(f"locate after restart={located.reason if located else None}")
                if located is None or located.travel_id != travel_id:
                    raise CheckFailure("travel receipt missing after restart")
                node = reopened.memory.retrieve_memory_node(
                    event_id, requester=memory_id
                )
                if node is None:
                    raise CheckFailure("destination EVENT missing after restart")
                details["restart_recovered"] = True
            finally:
                reopened.memory.shutdown()
                reopened.firewall.close()
                reopened.persistence.close()
        finally:
            _close_highway(origin)
            _close_highway(hop)
            if dest is not None:
                _close_highway(dest)


def check_dht_index_optional_and_unbound_to_firewall(
    details: dict[str, object],
) -> None:
    """DHT travel index is optional and is not a second firewall."""
    with tempfile.TemporaryDirectory(prefix="hwy_dht_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        origin, hop, dest = _pair_three(str(root / "mesh"))
        dht_store = PANPersistenceStore(base_path=root / "dht")
        dht = DHTNode(
            origin.pan_identity,
            persistence=dht_store,
            enable_consensus=False,
            enable_registries=False,
        )
        try:
            if hasattr(dht, "firewall"):
                raise CheckFailure("DHTNode grew a firewall attribute")
            origin.dht = dht
            node_id = _seed_node(origin, CARGO_CLAIM)
            ticket = origin.embark(dest.pan_identity, [node_id], via=())
            indexed = dht.lookup(f"highway:travel:{ticket.travel_id}")
            print(f"dht index present={indexed is not None}")
            if not isinstance(indexed, dict):
                raise CheckFailure("optional DHT index was not written")
            located = origin.locate(ticket.travel_id)
            if located is None:
                raise CheckFailure("locate missed DHT/receipt index")
            details["dht_indexed"] = True
            details["dht_unbound_to_firewall"] = True
        finally:
            _close_three(origin, hop, dest)
            dht_store.close()


CHECKS: tuple[tuple[str, CheckFn], ...] = (
    ("source_has_no_legacy_mesh", check_source_has_no_legacy_mesh),
    ("requires_explicit_firewall", check_requires_explicit_firewall),
    ("direct_travel_sealed_cargo", check_direct_travel_sealed_cargo),
    ("multi_hop_three_nodes", check_multi_hop_three_nodes),
    ("firewall_blocks_telemetry_on_hop", check_firewall_blocks_telemetry_on_hop),
    ("legacy_routing_key_rejected", check_legacy_routing_key_rejected),
    ("identity_blocklist_stops_travel", check_identity_blocklist_stops_travel),
    ("bad_usms_signature_fails_loud", check_bad_usms_signature_fails_loud),
    ("cargo_survives_restart", check_cargo_survives_restart),
    ("dht_index_optional_and_unbound_to_firewall", check_dht_index_optional_and_unbound_to_firewall),
)


def run() -> dict[str, object]:
    """Execute every highway check and return a gate-shaped payload."""
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
            HighwayError,
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
        "name": "planetary_highway",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} highway checks failed"
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
        f"# Planetary highway run {timestamp}",
        "",
        f"I ran `python test/highway/test_planetary_highway.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required identity-hash hops, cargo RSA-sealed to the destination,",
        "blind relays, a real firewall, and no pickle/UDP/ARFS second internet.",
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
        print(f"highway consumer start {timestamp}")
        payload = run()
        print(f"highway consumer status={payload.get('status')}")
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
