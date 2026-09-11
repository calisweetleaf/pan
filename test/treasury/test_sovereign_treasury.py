"""Direct consumer for the sovereign treasury FSM.

Real tempdir SQLite via PANPersistenceStore and DHTNode. No mocks.
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

from PAN_SDK import DHTNode, PANPersistenceStore, SovereignIdentity
from PAN_SDK.treasury import (
    NetworkTelemetry,
    ProposalKind,
    TreasuryContractRejected,
    TreasuryError,
    TreasuryState,
    TreasuryStateError,
    build_proof,
)


class CheckFailure(Exception):
    """A named treasury check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _three_identities() -> tuple[SovereignIdentity, SovereignIdentity, SovereignIdentity]:
    """Create three distinct PAN validators."""
    return (
        SovereignIdentity("FedChair"),
        SovereignIdentity("VerifierOne"),
        SovereignIdentity("VerifierTwo"),
    )


def _open_node(tmpdir: str, identity: SovereignIdentity) -> DHTNode:
    """Open a DHT node with persistence under tmpdir."""
    store = PANPersistenceStore(base_path=Path(tmpdir) / "pan")
    return DHTNode(identity, persistence=store, enable_consensus=False)


def _pass_votes(treasury: object, proposal_id: str, voters: tuple[SovereignIdentity, ...]) -> None:
    """Cast yes votes from every validator."""
    for voter in voters:
        treasury.vote(proposal_id, voter.identity_hash, True)


def check_genesis_rejects_mint(details: dict[str, object]) -> None:
    """MINT proposals are illegal before genesis is sealed."""
    chair, one, two = _three_identities()
    with tempfile.TemporaryDirectory(prefix="treas_genesis_") as tmpdir:
        node = _open_node(tmpdir, chair)
        treasury = node.treasury
        try:
            treasury.register_validator(chair.identity_hash)
            treasury.register_validator(one.identity_hash)
            treasury.register_validator(two.identity_hash)
            try:
                treasury.submit_proposal(chair.identity_hash, ProposalKind.MINT, {"amount": 1})
                raise CheckFailure("MINT was accepted during GENESIS")
            except TreasuryStateError as exc:
                print(f"genesis blocked mint: {exc}")
            details["state"] = treasury.state.value
            if treasury.state is not TreasuryState.GENESIS:
                raise CheckFailure("treasury left GENESIS too early")
        finally:
            node.persistence.close()


def check_seal_genesis_and_contract_reject(details: dict[str, object]) -> None:
    """Three validators seal genesis; solidity payloads are rejected."""
    chair, one, two = _three_identities()
    with tempfile.TemporaryDirectory(prefix="treas_seal_") as tmpdir:
        node = _open_node(tmpdir, chair)
        treasury = node.treasury
        try:
            treasury.register_validator(chair.identity_hash)
            treasury.register_validator(one.identity_hash)
            treasury.register_validator(two.identity_hash)
            result = treasury.seal_genesis(chair.identity_hash)
            print(f"seal_genesis status={result.status} state={result.state.value}")
            if result.state is not TreasuryState.MINT_PHASE:
                raise CheckFailure("genesis did not enter MINT_PHASE")
            try:
                treasury.submit_proposal(
                    chair.identity_hash,
                    ProposalKind.MINT,
                    {
                        "recipient_id": one.identity_hash,
                        "amount": 10,
                        "bytecode": "0x6001600055",
                        "solidity": "pragma solidity ^0.8.0",
                    },
                )
                raise CheckFailure("smart contract payload was accepted")
            except TreasuryContractRejected as exc:
                print(f"contract rejected: {exc}")
            details["state"] = treasury.state.value
            details["quorum"] = treasury.quorum_threshold()
            if details["quorum"] != 3:
                raise CheckFailure(f"expected quorum 3, got {details['quorum']}")
        finally:
            node.persistence.close()


def check_poi_mint_requires_quorum(details: dict[str, object]) -> None:
    """Chair cannot unilaterally mint; PoI plus three votes mints onto the ledger."""
    chair, one, two = _three_identities()
    with tempfile.TemporaryDirectory(prefix="treas_mint_") as tmpdir:
        node = _open_node(tmpdir, chair)
        treasury = node.treasury
        try:
            for identity in (chair, one, two):
                treasury.register_validator(identity.identity_hash)
            treasury.seal_genesis(chair.identity_hash)
            proof = build_proof(
                worker_identity_hash=one.identity_hash,
                prompt="infer:civic-cycle-1",
                output="commitment-output-1",
                verifier_identity_hashes=(chair.identity_hash, two.identity_hash),
            )
            proposal = treasury.submit_proposal(
                one.identity_hash,
                ProposalKind.MINT,
                {
                    "recipient_id": one.identity_hash,
                    "amount": 40,
                    "poi": proof.to_mapping(),
                },
            )
            treasury.vote(proposal.proposal_id, chair.identity_hash, True)
            unilateral = treasury.execute_proposal(proposal.proposal_id)
            print(f"unilateral execute={unilateral.status} reason={unilateral.reason}")
            if unilateral.ok:
                raise CheckFailure("chair-plus-nothing executed a mint")
            if unilateral.reason not in {"quorum_not_met", "chair_cannot_unilaterally_execute"}:
                raise CheckFailure(f"unexpected rejection: {unilateral.reason}")
            _pass_votes(treasury, proposal.proposal_id, (chair, one, two))
            executed = treasury.execute_proposal(proposal.proposal_id)
            print(f"quorum mint status={executed.status} supply={node.economic_engine.token_supply}")
            if not executed.ok:
                raise CheckFailure(f"quorum mint failed: {executed.reason}")
            balance = node.economic_engine.get_balance(one.identity_hash)
            if balance != 40:
                raise CheckFailure(f"expected balance 40, got {balance}")
            details["minted_balance"] = balance
            details["packet_id"] = executed.details.get("packet_id")
        finally:
            node.persistence.close()


def check_distribute_and_burn_and_halts(details: dict[str, object]) -> None:
    """Telemetry gates DISTRIBUTE; burn works in BURN_CYCLE; halts freeze mint."""
    chair, one, two = _three_identities()
    with tempfile.TemporaryDirectory(prefix="treas_flow_") as tmpdir:
        node = _open_node(tmpdir, chair)
        treasury = node.treasury
        try:
            for identity in (chair, one, two):
                treasury.register_validator(identity.identity_hash)
            treasury.seal_genesis(chair.identity_hash)
            proof = build_proof(
                worker_identity_hash=two.identity_hash,
                prompt="infer:reserve-fill",
                output="reserve-output",
                verifier_identity_hashes=(chair.identity_hash, one.identity_hash),
            )
            mint = treasury.submit_proposal(
                two.identity_hash,
                ProposalKind.MINT,
                {
                    "recipient_id": node.economic_engine.treasury_account_id,
                    "amount": 100,
                    "poi": proof.to_mapping(),
                },
            )
            _pass_votes(treasury, mint.proposal_id, (chair, one, two))
            minted = treasury.execute_proposal(mint.proposal_id)
            if not minted.ok:
                raise CheckFailure(f"reserve mint failed: {minted.reason}")

            try:
                treasury.submit_proposal(
                    chair.identity_hash,
                    ProposalKind.TRANSITION,
                    {"target_state": TreasuryState.DISTRIBUTE.value},
                )
                # submit succeeds; execute must fail without telemetry
            except TreasuryStateError as exc:
                raise CheckFailure(f"transition submit should be legal: {exc}") from exc
            # The last submit created a proposal. Find it.
            open_ids = [
                item.proposal_id
                for item in treasury.proposals.values()
                if item.kind is ProposalKind.TRANSITION and item.status.value == "OPEN"
            ]
            if not open_ids:
                raise CheckFailure("missing TRANSITION proposal")
            _pass_votes(treasury, open_ids[-1], (chair, one, two))
            try:
                treasury.execute_proposal(open_ids[-1])
                raise CheckFailure("DISTRIBUTE transition succeeded without telemetry")
            except TreasuryStateError as exc:
                print(f"distribute blocked without telemetry: {exc}")

            treasury.seal_telemetry(
                NetworkTelemetry(
                    bandwidth_provisioned=2048,
                    inference_cycles=12,
                    active_citizens=3,
                )
            )
            transition = treasury.submit_proposal(
                chair.identity_hash,
                ProposalKind.TRANSITION,
                {"target_state": TreasuryState.DISTRIBUTE.value},
            )
            _pass_votes(treasury, transition.proposal_id, (chair, one, two))
            moved = treasury.execute_proposal(transition.proposal_id)
            print(f"to DISTRIBUTE status={moved.status} state={treasury.state.value}")
            if treasury.state is not TreasuryState.DISTRIBUTE:
                raise CheckFailure("failed to enter DISTRIBUTE")

            dist = treasury.submit_proposal(
                one.identity_hash,
                ProposalKind.DISTRIBUTE,
                {"recipient_id": one.identity_hash, "amount": 25},
            )
            _pass_votes(treasury, dist.proposal_id, (chair, one, two))
            distributed = treasury.execute_proposal(dist.proposal_id)
            if not distributed.ok:
                raise CheckFailure(f"distribute failed: {distributed.reason}")
            citizen_balance = node.economic_engine.get_balance(one.identity_hash)
            print(f"citizen after distribute={citizen_balance}")
            if citizen_balance != 25:
                raise CheckFailure(f"expected citizen 25, got {citizen_balance}")

            to_mint = treasury.submit_proposal(
                chair.identity_hash,
                ProposalKind.TRANSITION,
                {"target_state": TreasuryState.MINT_PHASE.value},
            )
            _pass_votes(treasury, to_mint.proposal_id, (chair, one, two))
            treasury.execute_proposal(to_mint.proposal_id)
            to_burn = treasury.submit_proposal(
                chair.identity_hash,
                ProposalKind.TRANSITION,
                {"target_state": TreasuryState.BURN_CYCLE.value},
            )
            _pass_votes(treasury, to_burn.proposal_id, (chair, one, two))
            treasury.execute_proposal(to_burn.proposal_id)
            if treasury.state is not TreasuryState.BURN_CYCLE:
                raise CheckFailure("failed to enter BURN_CYCLE")
            burn = treasury.submit_proposal(
                one.identity_hash,
                ProposalKind.BURN,
                {"account_id": one.identity_hash, "amount": 10},
            )
            _pass_votes(treasury, burn.proposal_id, (chair, one, two))
            burned = treasury.execute_proposal(burn.proposal_id)
            if not burned.ok:
                raise CheckFailure(f"burn failed: {burned.reason}")
            after_burn = node.economic_engine.get_balance(one.identity_hash)
            print(f"citizen after burn={after_burn} supply={node.economic_engine.token_supply}")
            if after_burn != 15:
                raise CheckFailure(f"expected 15 after burn, got {after_burn}")

            to_audit = treasury.submit_proposal(
                chair.identity_hash,
                ProposalKind.TRANSITION,
                {"target_state": TreasuryState.AUDIT_HALT.value},
            )
            _pass_votes(treasury, to_audit.proposal_id, (chair, one, two))
            treasury.execute_proposal(to_audit.proposal_id)
            try:
                treasury.submit_proposal(
                    one.identity_hash,
                    ProposalKind.MINT,
                    {"recipient_id": one.identity_hash, "amount": 1},
                )
                raise CheckFailure("MINT accepted during AUDIT_HALT")
            except TreasuryStateError as exc:
                print(f"audit halt blocked mint: {exc}")

            to_suspend = treasury.submit_proposal(
                chair.identity_hash,
                ProposalKind.TRANSITION,
                {"target_state": TreasuryState.CRITICAL_SUSPEND.value},
            )
            _pass_votes(treasury, to_suspend.proposal_id, (chair, one, two))
            treasury.execute_proposal(to_suspend.proposal_id)
            if treasury.state is not TreasuryState.CRITICAL_SUSPEND:
                raise CheckFailure("failed to enter CRITICAL_SUSPEND")
            details["final_state"] = treasury.state.value
            details["supply"] = node.economic_engine.token_supply
            details["citizen_balance"] = after_burn
        finally:
            node.persistence.close()


def check_restart_hydrates_fsm(details: dict[str, object]) -> None:
    """Treasury state and validators survive DHTNode reopen on the same sqlite."""
    chair, one, two = _three_identities()
    pem = chair.serialize_private_key()
    with tempfile.TemporaryDirectory(prefix="treas_restart_") as tmpdir:
        first = _open_node(tmpdir, chair)
        try:
            treasury = first.treasury
            for identity in (chair, one, two):
                treasury.register_validator(identity.identity_hash)
            treasury.seal_genesis(chair.identity_hash)
            details["state_before"] = treasury.state.value
            details["chair_before"] = treasury.fed_chair_id
        finally:
            first.persistence.close()

        restored = SovereignIdentity("FedChair", private_key_pem=pem)
        second = _open_node(tmpdir, restored)
        try:
            treasury = second.treasury
            print(
                f"reopened state={treasury.state.value} "
                f"validators={len(treasury.validators)} chair={(treasury.fed_chair_id or '')[:12]}"
            )
            if treasury.state is not TreasuryState.MINT_PHASE:
                raise CheckFailure("FSM did not hydrate MINT_PHASE")
            if len(treasury.validators) != 3:
                raise CheckFailure("validators did not hydrate")
            if treasury.fed_chair_id != restored.identity_hash:
                raise CheckFailure("fed chair did not hydrate")
            details["state_after"] = treasury.state.value
            details["validators_after"] = len(treasury.validators)
        finally:
            second.persistence.close()


CHECKS = (
    ("genesis_rejects_mint", check_genesis_rejects_mint),
    ("seal_genesis_and_contract_reject", check_seal_genesis_and_contract_reject),
    ("poi_mint_requires_quorum", check_poi_mint_requires_quorum),
    ("distribute_and_burn_and_halts", check_distribute_and_burn_and_halts),
    ("restart_hydrates_fsm", check_restart_hydrates_fsm),
)


def run() -> dict[str, object]:
    """Execute every treasury check and return a gate-shaped payload."""
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
            TreasuryError,
            TreasuryStateError,
            TreasuryContractRejected,
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
        "name": "sovereign_treasury",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} treasury checks failed"
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
        f"# Sovereign treasury run {timestamp}",
        "",
        f"I ran `python test/treasury/test_sovereign_treasury.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required a rigid FSM, Proof-of-Inference minting, ceil(n/2)+1 quorum,",
        "smart-contract rejection, and sqlite hydrate after reopen.",
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
        print(f"treasury consumer start {timestamp}")
        payload = run()
        print(f"treasury consumer status={payload.get('status')}")
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
