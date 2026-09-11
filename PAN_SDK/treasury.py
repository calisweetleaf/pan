"""
Sovereign Treasury — rigid finite-state federal reserve for PAN.

Source: docs/research/Building a Sovereign Digital Nation.md section 4
Integrated: 2026-09-10
Purpose: Deterministic GENESIS/MINT_PHASE/BURN_CYCLE/DISTRIBUTE/AUDIT_HALT/
    CRITICAL_SUSPEND machine. Token allocation requires Proof-of-Inference.
    The Elected Fed Chair proposes; ceil(n/2)+1 validators execute. Turing-complete
    smart contracts are rejected at the proposal boundary.
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PAN_SDK.PAN_SDK import (
    PANEconomicEngine,
    PANPersistenceStore,
    SovereignCommunicator,
    SovereignIdentity,
    canonical,
    sha256_hex,
    utc_now_iso,
)

LOGGER = logging.getLogger("SovereignTreasury")

GENESIS_VALIDATOR_MINIMUM = 3
DISTRIBUTE_MIN_INFERENCE_CYCLES = 1
TREASURY_PACKET_KIND = "TREASURY_LEDGER"

FORBIDDEN_CONTRACT_KEYS = frozenset(
    {
        "bytecode",
        "contract_source",
        "evm",
        "opcode",
        "opcodes",
        "smart_contract",
        "solidity",
        "vyper",
        "wasm",
        "webassembly",
    }
)

FORBIDDEN_CONTRACT_PATTERN_HINTS = (
    "pragma solidity",
    "-----begin evm",
    "opcode:",
    "(module",  # wasm
)


class TreasuryError(Exception):
    """Domain error for the sovereign treasury."""


class TreasuryStateError(TreasuryError):
    """Raised when an action is illegal in the current FSM state."""


class TreasuryProofError(TreasuryError):
    """Raised when Proof-of-Inference fails verification."""


class TreasuryContractRejected(TreasuryError):
    """Raised when a proposal smuggles Turing-complete contract material."""


class TreasuryProposalError(TreasuryError):
    """Raised when a proposal cannot be found or is not executable."""


class TreasuryState(str, Enum):
    """Exclusive treasury states. No other runtime exists."""

    GENESIS = "GENESIS"
    MINT_PHASE = "MINT_PHASE"
    BURN_CYCLE = "BURN_CYCLE"
    DISTRIBUTE = "DISTRIBUTE"
    AUDIT_HALT = "AUDIT_HALT"
    CRITICAL_SUSPEND = "CRITICAL_SUSPEND"


class ProposalKind(str, Enum):
    """Symbolic proposal kinds. There is no generic contract VM."""

    TRANSITION = "TRANSITION"
    MINT = "MINT"
    BURN = "BURN"
    DISTRIBUTE = "DISTRIBUTE"
    ELECT_CHAIR = "ELECT_CHAIR"
    ADJUST_EMISSION = "ADJUST_EMISSION"
    ADD_VALIDATOR = "ADD_VALIDATOR"


class ProposalStatus(str, Enum):
    """Proposal lifecycle."""

    OPEN = "OPEN"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ProofOfInference:
    """Deterministic inference commitment plus independent verifier attestations."""

    request_hash: str
    result_hash: str
    worker_identity_hash: str
    prompt: str
    output: str
    verifier_identity_hashes: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        """Serialize for persistence and hashing."""
        return {
            "request_hash": self.request_hash,
            "result_hash": self.result_hash,
            "worker_identity_hash": self.worker_identity_hash,
            "prompt": self.prompt,
            "output": self.output,
            "verifier_identity_hashes": list(self.verifier_identity_hashes),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ProofOfInference:
        """Rebuild a proof from a stored mapping."""
        verifiers_raw = payload.get("verifier_identity_hashes") or []
        if not isinstance(verifiers_raw, list):
            raise TreasuryProofError("verifier_identity_hashes must be a list")
        return cls(
            request_hash=str(payload.get("request_hash") or ""),
            result_hash=str(payload.get("result_hash") or ""),
            worker_identity_hash=str(payload.get("worker_identity_hash") or ""),
            prompt=str(payload.get("prompt") or ""),
            output=str(payload.get("output") or ""),
            verifier_identity_hashes=tuple(str(item) for item in verifiers_raw),
        )


@dataclass
class NetworkTelemetry:
    """Sealed network facts that gate DISTRIBUTE."""

    bandwidth_provisioned: int
    inference_cycles: int
    active_citizens: int
    recorded_at: str = field(default_factory=utc_now_iso)

    def to_mapping(self) -> dict[str, object]:
        """Serialize telemetry."""
        return {
            "bandwidth_provisioned": self.bandwidth_provisioned,
            "inference_cycles": self.inference_cycles,
            "active_citizens": self.active_citizens,
            "recorded_at": self.recorded_at,
        }


@dataclass
class TreasuryResult:
    """Structured outcome for vote/execute paths that can lawfully no-op."""

    status: str
    reason: str
    state: TreasuryState
    proposal_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True when the action committed."""
        return self.status == "ok"


@dataclass
class TreasuryProposal:
    """One symbolic proposal. Payload is data, never code."""

    proposal_id: str
    kind: ProposalKind
    proposer_id: str
    payload: dict[str, object]
    created_at: str
    status: ProposalStatus = ProposalStatus.OPEN
    votes: dict[str, bool] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, object]:
        """Serialize the proposal including votes."""
        return {
            "proposal_id": self.proposal_id,
            "kind": self.kind.value,
            "proposer_id": self.proposer_id,
            "payload": dict(self.payload),
            "created_at": self.created_at,
            "status": self.status.value,
            "votes": dict(self.votes),
        }


LEGAL_TRANSITIONS: dict[TreasuryState, frozenset[TreasuryState]] = {
    TreasuryState.GENESIS: frozenset({TreasuryState.MINT_PHASE}),
    TreasuryState.MINT_PHASE: frozenset(
        {
            TreasuryState.BURN_CYCLE,
            TreasuryState.DISTRIBUTE,
            TreasuryState.AUDIT_HALT,
            TreasuryState.CRITICAL_SUSPEND,
        }
    ),
    TreasuryState.BURN_CYCLE: frozenset(
        {
            TreasuryState.MINT_PHASE,
            TreasuryState.AUDIT_HALT,
            TreasuryState.CRITICAL_SUSPEND,
        }
    ),
    TreasuryState.DISTRIBUTE: frozenset(
        {
            TreasuryState.MINT_PHASE,
            TreasuryState.AUDIT_HALT,
            TreasuryState.CRITICAL_SUSPEND,
        }
    ),
    TreasuryState.AUDIT_HALT: frozenset(
        {TreasuryState.MINT_PHASE, TreasuryState.CRITICAL_SUSPEND}
    ),
    TreasuryState.CRITICAL_SUSPEND: frozenset({TreasuryState.AUDIT_HALT}),
}


class SovereignTreasury:
    """Finite-state macroeconomic engine. No smart-contract VM exists here."""

    def __init__(
        self,
        identity: SovereignIdentity,
        persistence: PANPersistenceStore,
        economic_engine: PANEconomicEngine,
    ) -> None:
        """
        Bind the treasury FSM to PAN identity, sqlite persistence, and the live ledger.

        Args:
            identity: Node operator identity. Signs treasury ledger packets.
            persistence: SQLite-backed PAN persistence store.
            economic_engine: Single supply/account truth. Mint and burn land here.

        Returns:
            None
        """
        if identity is None:
            raise TreasuryError("SovereignTreasury requires a SovereignIdentity")
        if persistence is None:
            raise TreasuryError("SovereignTreasury requires PANPersistenceStore")
        if economic_engine is None:
            raise TreasuryError("SovereignTreasury requires PANEconomicEngine")
        self.identity = identity
        self.persistence = persistence
        self.economic_engine = economic_engine
        self.communicator = SovereignCommunicator(identity)
        self._lock = threading.RLock()
        self.state = TreasuryState.GENESIS
        self.fed_chair_id: str | None = None
        self.emission_rate: int = 1
        self.validators: dict[str, int] = {}
        self.proposals: dict[str, TreasuryProposal] = {}
        self.telemetry: NetworkTelemetry | None = None
        self.hydrate_from_persistence()
        LOGGER.info(
            "SovereignTreasury online state=%s chair=%s validators=%s",
            self.state.value,
            (self.fed_chair_id or "")[:12],
            len(self.validators),
        )

    def hydrate_from_persistence(self) -> None:
        """
        Reload FSM, validators, proposals, and telemetry from sqlite.

        Args:
            None

        Returns:
            None
        """
        meta = self.persistence.read_state("treasury_fsm", "meta")
        if isinstance(meta, dict):
            state_raw = str(meta.get("state") or TreasuryState.GENESIS.value)
            self.state = TreasuryState(state_raw)
            chair = meta.get("fed_chair_id")
            self.fed_chair_id = str(chair) if chair else None
            self.emission_rate = int(meta.get("emission_rate") or 1)
        validators = self.persistence.load_component("treasury_validators")
        if validators:
            self.validators = {str(key): int(value) for key, value in validators.items()}
        stored_proposals = self.persistence.load_component("treasury_proposals")
        self.proposals = {}
        for proposal_id, raw in stored_proposals.items():
            if not isinstance(raw, dict):
                continue
            payload_raw = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
            votes_raw = raw.get("votes") if isinstance(raw.get("votes"), dict) else {}
            self.proposals[str(proposal_id)] = TreasuryProposal(
                proposal_id=str(raw.get("proposal_id") or proposal_id),
                kind=ProposalKind(str(raw.get("kind"))),
                proposer_id=str(raw.get("proposer_id") or ""),
                payload=dict(payload_raw) if isinstance(payload_raw, dict) else {},
                created_at=str(raw.get("created_at") or utc_now_iso()),
                status=ProposalStatus(str(raw.get("status") or ProposalStatus.OPEN.value)),
                votes={str(voter): bool(choice) for voter, choice in votes_raw.items()},
            )
        telemetry_raw = self.persistence.read_state("treasury_fsm", "telemetry")
        if isinstance(telemetry_raw, dict):
            self.telemetry = NetworkTelemetry(
                bandwidth_provisioned=int(telemetry_raw.get("bandwidth_provisioned") or 0),
                inference_cycles=int(telemetry_raw.get("inference_cycles") or 0),
                active_citizens=int(telemetry_raw.get("active_citizens") or 0),
                recorded_at=str(telemetry_raw.get("recorded_at") or utc_now_iso()),
            )

    def get_status(self) -> dict[str, object]:
        """
        Return a snapshot of the live FSM.

        Args:
            None

        Returns:
            Status mapping for operators and tests.
        """
        return {
            "state": self.state.value,
            "fed_chair_id": self.fed_chair_id,
            "emission_rate": self.emission_rate,
            "validator_count": len(self.validators),
            "quorum": self.quorum_threshold(),
            "open_proposals": sum(
                1 for item in self.proposals.values() if item.status is ProposalStatus.OPEN
            ),
            "token_supply": self.economic_engine.token_supply,
            "treasury_balance": self.economic_engine.get_balance(
                self.economic_engine.treasury_account_id
            ),
        }

    def quorum_threshold(self) -> int:
        """
        Return ceil(n/2)+1 for the current validator set.

        Args:
            None

        Returns:
            Votes required to execute. Zero validators yields an unreachable 1.
        """
        count = len(self.validators)
        if count < 1:
            return 1
        return (count + 1) // 2 + 1

    def register_validator(self, identity_hash: str, voting_power: int = 1) -> None:
        """
        Register a validator during GENESIS only.

        Args:
            identity_hash: PAN identity hash.
            voting_power: Positive integer weight. Currently counted as one head for quorum.

        Returns:
            None
        """
        if self.state is not TreasuryState.GENESIS:
            raise TreasuryStateError("validators may be registered only during GENESIS")
        if not identity_hash or not isinstance(identity_hash, str):
            raise TreasuryError("validator identity_hash must be a non-empty string")
        if voting_power < 1:
            raise TreasuryError("voting_power must be >= 1")
        with self._lock:
            self.validators[identity_hash] = voting_power
            self._persist_validators()
            self._persist_meta()
        LOGGER.info("Registered treasury validator %s", identity_hash[:12])

    def seal_genesis(self, founding_chair_id: str) -> TreasuryResult:
        """
        Leave GENESIS for MINT_PHASE once three validators and a chair exist.

        Args:
            founding_chair_id: Validator who becomes the first Fed Chair proposer.

        Returns:
            TreasuryResult. Raises if the boolean genesis matrix is not satisfied.
        """
        with self._lock:
            if self.state is not TreasuryState.GENESIS:
                raise TreasuryStateError("seal_genesis is only legal in GENESIS")
            if len(self.validators) < GENESIS_VALIDATOR_MINIMUM:
                raise TreasuryStateError(
                    f"genesis requires {GENESIS_VALIDATOR_MINIMUM} validators"
                )
            if founding_chair_id not in self.validators:
                raise TreasuryStateError("founding chair must be a registered validator")
            self.fed_chair_id = founding_chair_id
            self.state = TreasuryState.MINT_PHASE
            self._persist_meta()
            self._journal("genesis_sealed", {"chair": founding_chair_id})
            return TreasuryResult(
                status="ok",
                reason="genesis_sealed",
                state=self.state,
                details={"validators": len(self.validators)},
            )

    def seal_telemetry(self, telemetry: NetworkTelemetry) -> None:
        """
        Record sealed network telemetry used by DISTRIBUTE transitions.

        Args:
            telemetry: Non-negative bandwidth, inference cycles, and citizen counts.

        Returns:
            None
        """
        if telemetry.bandwidth_provisioned < 0 or telemetry.inference_cycles < 0:
            raise TreasuryError("telemetry counters cannot be negative")
        if telemetry.active_citizens < 0:
            raise TreasuryError("active_citizens cannot be negative")
        with self._lock:
            self.telemetry = telemetry
            self.persistence.write_state("treasury_fsm", "telemetry", telemetry.to_mapping())
            self._journal("telemetry_sealed", telemetry.to_mapping())

    def submit_proposal(
        self,
        proposer_id: str,
        kind: ProposalKind,
        payload: Mapping[str, object],
    ) -> TreasuryProposal:
        """
        Submit a symbolic proposal. The chair proposes transitions; any validator may mint.

        Args:
            proposer_id: Validator identity hash.
            kind: Proposal kind.
            payload: JSON-stable data. Contract keys are rejected.

        Returns:
            The OPEN proposal.
        """
        if proposer_id not in self.validators:
            raise TreasuryStateError("proposer is not a treasury validator")
        reject_contract_payload(payload)
        body = _jsonable_mapping(payload)
        with self._lock:
            self._assert_kind_legal(kind, proposer_id)
            proposal_id = sha256_hex(
                canonical(
                    {
                        "kind": kind.value,
                        "proposer": proposer_id,
                        "payload": body,
                        "created_at": utc_now_iso(),
                    }
                )
            )[:32]
            proposal = TreasuryProposal(
                proposal_id=proposal_id,
                kind=kind,
                proposer_id=proposer_id,
                payload=body,
                created_at=utc_now_iso(),
            )
            self.proposals[proposal_id] = proposal
            self._persist_proposal(proposal)
            self._journal(
                "proposal_submitted",
                {"proposal_id": proposal_id, "kind": kind.value},
            )
            return proposal

    def vote(self, proposal_id: str, voter_id: str, approve: bool) -> TreasuryResult:
        """
        Cast or replace a validator vote. Execution is a separate call.

        Args:
            proposal_id: Open proposal id.
            voter_id: Validator identity hash.
            approve: True to approve.

        Returns:
            TreasuryResult describing the live tally.
        """
        with self._lock:
            proposal = self._require_open_proposal(proposal_id)
            if voter_id not in self.validators:
                raise TreasuryStateError("voter is not a treasury validator")
            proposal.votes[voter_id] = bool(approve)
            self._persist_proposal(proposal)
            approvals = sum(1 for choice in proposal.votes.values() if choice)
            return TreasuryResult(
                status="ok",
                reason="vote_recorded",
                state=self.state,
                proposal_id=proposal_id,
                details={
                    "approvals": approvals,
                    "quorum": self.quorum_threshold(),
                    "approve": bool(approve),
                },
            )

    def execute_proposal(self, proposal_id: str) -> TreasuryResult:
        """
        Execute an OPEN proposal if and only if the quorum matrix is satisfied.

        Args:
            proposal_id: Proposal to execute.

        Returns:
            TreasuryResult. Rejected (not raised) when quorum is missing so votes can accumulate.
        """
        with self._lock:
            proposal = self._require_open_proposal(proposal_id)
            approvals = [voter for voter, choice in proposal.votes.items() if choice]
            needed = self.quorum_threshold()
            if len(approvals) < needed:
                return TreasuryResult(
                    status="rejected",
                    reason="quorum_not_met",
                    state=self.state,
                    proposal_id=proposal_id,
                    details={"approvals": len(approvals), "quorum": needed},
                )
            if len(approvals) == 1 and approvals[0] == proposal.proposer_id:
                return TreasuryResult(
                    status="rejected",
                    reason="chair_cannot_unilaterally_execute",
                    state=self.state,
                    proposal_id=proposal_id,
                )
            self._apply_proposal(proposal)
            proposal.status = ProposalStatus.EXECUTED
            self._persist_proposal(proposal)
            self._persist_meta()
            packet = self.communicator.create_packet(
                TREASURY_PACKET_KIND,
                {
                    "proposal_id": proposal.proposal_id,
                    "kind": proposal.kind.value,
                    "state": self.state.value,
                    "payload_digest": sha256_hex(canonical(proposal.payload)),
                },
            )
            self.persistence.write_state(
                "treasury_packets", packet.packet_id, packet.to_dict()
            )
            self._journal(
                "proposal_executed",
                {
                    "proposal_id": proposal.proposal_id,
                    "kind": proposal.kind.value,
                    "packet_id": packet.packet_id,
                },
            )
            return TreasuryResult(
                status="ok",
                reason="executed",
                state=self.state,
                proposal_id=proposal.proposal_id,
                details={"packet_id": packet.packet_id},
            )

    def verify_proof_of_inference(self, proof: ProofOfInference) -> str:
        """
        Re-execute the deterministic inference commitment and demand quorum verifiers.

        Args:
            proof: Worker output plus independent validator attestations.

        Returns:
            The verified result_hash.

        Raises:
            TreasuryProofError: if hashes diverge or verifiers are insufficient.
        """
        if proof.worker_identity_hash not in self.validators:
            raise TreasuryProofError("PoI worker is not a treasury validator")
        request_hash = sha256_hex(proof.prompt)
        if request_hash != proof.request_hash:
            raise TreasuryProofError("request_hash does not match the prompt")
        commitment = inference_commitment(proof.prompt, proof.output)
        if commitment != proof.result_hash:
            raise TreasuryProofError(
                "result_hash diverged from deterministic re-execution"
            )
        unique_verifiers = []
        seen: set[str] = set()
        for verifier in proof.verifier_identity_hashes:
            if verifier not in self.validators:
                raise TreasuryProofError("PoI verifier is not a treasury validator")
            if verifier == proof.worker_identity_hash:
                continue
            if verifier in seen:
                continue
            seen.add(verifier)
            unique_verifiers.append(verifier)
        needed = self.quorum_threshold()
        if len(unique_verifiers) + 1 < needed:
            raise TreasuryProofError(
                f"PoI requires {needed} distinct validator attestations including the worker"
            )
        if len(unique_verifiers) < max(1, needed - 1):
            raise TreasuryProofError("PoI lacks independent verifier quorum")
        return commitment

    def _assert_kind_legal(self, kind: ProposalKind, proposer_id: str) -> None:
        """Reject kinds that the current state or proposer cannot touch."""
        if self.state is TreasuryState.GENESIS:
            raise TreasuryStateError("proposals are illegal before genesis is sealed")
        if self.state is TreasuryState.CRITICAL_SUSPEND and kind is not ProposalKind.TRANSITION:
            raise TreasuryStateError("CRITICAL_SUSPEND accepts only TRANSITION proposals")
        if self.state is TreasuryState.AUDIT_HALT and kind not in {
            ProposalKind.TRANSITION,
            ProposalKind.ELECT_CHAIR,
        }:
            raise TreasuryStateError("AUDIT_HALT accepts only TRANSITION or ELECT_CHAIR")
        if kind is ProposalKind.MINT and self.state is not TreasuryState.MINT_PHASE:
            raise TreasuryStateError("MINT is legal only in MINT_PHASE")
        if kind is ProposalKind.BURN and self.state is not TreasuryState.BURN_CYCLE:
            raise TreasuryStateError("BURN is legal only in BURN_CYCLE")
        if kind is ProposalKind.DISTRIBUTE and self.state is not TreasuryState.DISTRIBUTE:
            raise TreasuryStateError("DISTRIBUTE is legal only in DISTRIBUTE")
        chair_only = {
            ProposalKind.TRANSITION,
            ProposalKind.ADJUST_EMISSION,
        }
        if kind in chair_only and proposer_id != self.fed_chair_id:
            raise TreasuryStateError("only the Fed Chair may propose this kind")

    def _apply_proposal(self, proposal: TreasuryProposal) -> None:
        """Apply one executed proposal. Called with the treasury lock held."""
        if proposal.kind is ProposalKind.TRANSITION:
            target = TreasuryState(str(proposal.payload.get("target_state") or ""))
            if target not in LEGAL_TRANSITIONS[self.state]:
                raise TreasuryStateError(
                    f"{self.state.value} cannot transition to {target.value}"
                )
            if target is TreasuryState.DISTRIBUTE:
                self._require_distribute_telemetry()
            self.state = target
            return
        if proposal.kind is ProposalKind.ELECT_CHAIR:
            candidate = str(proposal.payload.get("candidate_id") or "")
            if candidate not in self.validators:
                raise TreasuryStateError("chair candidate is not a validator")
            self.fed_chair_id = candidate
            return
        if proposal.kind is ProposalKind.ADJUST_EMISSION:
            rate = int(proposal.payload.get("emission_rate") or 0)
            if rate < 1:
                raise TreasuryError("emission_rate must be >= 1")
            self.emission_rate = rate
            return
        if proposal.kind is ProposalKind.ADD_VALIDATOR:
            if self.state is not TreasuryState.MINT_PHASE:
                raise TreasuryStateError("ADD_VALIDATOR is legal only in MINT_PHASE")
            identity_hash = str(proposal.payload.get("identity_hash") or "")
            power = int(proposal.payload.get("voting_power") or 1)
            if not identity_hash or power < 1:
                raise TreasuryError("ADD_VALIDATOR payload is invalid")
            self.validators[identity_hash] = power
            self._persist_validators()
            return
        if proposal.kind is ProposalKind.MINT:
            self._apply_mint(proposal.payload)
            return
        if proposal.kind is ProposalKind.BURN:
            self._apply_burn(proposal.payload)
            return
        if proposal.kind is ProposalKind.DISTRIBUTE:
            self._apply_distribute(proposal.payload)
            return
        raise TreasuryProposalError(f"unhandled proposal kind {proposal.kind.value}")

    def _apply_mint(self, payload: Mapping[str, object]) -> None:
        """Mint only after Proof-of-Inference verification."""
        poi_raw = payload.get("poi")
        if not isinstance(poi_raw, dict):
            raise TreasuryProofError("MINT requires a poi mapping")
        proof = ProofOfInference.from_mapping(poi_raw)
        self.verify_proof_of_inference(proof)
        recipient = str(payload.get("recipient_id") or "")
        amount = int(payload.get("amount") or 0)
        if not recipient or amount < 1:
            raise TreasuryError("MINT requires recipient_id and positive amount")
        minted = amount * self.emission_rate
        ok = self.economic_engine.mint_tokens(recipient, minted, reason="proof_of_inference")
        if not ok:
            raise TreasuryError("economic engine refused mint")

    def _apply_burn(self, payload: Mapping[str, object]) -> None:
        """Burn tokens from an account during BURN_CYCLE."""
        account_id = str(payload.get("account_id") or "")
        amount = int(payload.get("amount") or 0)
        if not account_id or amount < 1:
            raise TreasuryError("BURN requires account_id and positive amount")
        ok = self.economic_engine.burn_tokens(account_id, amount, reason="treasury_burn")
        if not ok:
            raise TreasuryError("economic engine refused burn")

    def _apply_distribute(self, payload: Mapping[str, object]) -> None:
        """Move funds from the treasury account to a recipient."""
        self._require_distribute_telemetry()
        recipient = str(payload.get("recipient_id") or "")
        amount = int(payload.get("amount") or 0)
        if not recipient or amount < 1:
            raise TreasuryError("DISTRIBUTE requires recipient_id and positive amount")
        result = self.economic_engine.transfer_tokens(
            self.economic_engine.treasury_account_id,
            recipient,
            amount,
            "treasury_distribute",
            {"reason": "fsm_distribute"},
        )
        if not result.get("success"):
            raise TreasuryError(
                f"distribute failed: {result.get('error') or 'unknown ledger error'}"
            )

    def _require_distribute_telemetry(self) -> None:
        """DISTRIBUTE demands sealed telemetry with verified inference cycles."""
        if self.telemetry is None:
            raise TreasuryStateError("DISTRIBUTE requires sealed network telemetry")
        if self.telemetry.inference_cycles < DISTRIBUTE_MIN_INFERENCE_CYCLES:
            raise TreasuryStateError("DISTRIBUTE requires verified inference cycles")
        if self.telemetry.bandwidth_provisioned < 1:
            raise TreasuryStateError("DISTRIBUTE requires provisioned bandwidth")

    def _require_open_proposal(self, proposal_id: str) -> TreasuryProposal:
        """Return an OPEN proposal or fail loud."""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise TreasuryProposalError(f"unknown proposal {proposal_id}")
        if proposal.status is not ProposalStatus.OPEN:
            raise TreasuryProposalError(f"proposal {proposal_id} is {proposal.status.value}")
        return proposal

    def _persist_meta(self) -> None:
        """Write FSM meta to sqlite."""
        self.persistence.write_state(
            "treasury_fsm",
            "meta",
            {
                "state": self.state.value,
                "fed_chair_id": self.fed_chair_id,
                "emission_rate": self.emission_rate,
            },
        )

    def _persist_validators(self) -> None:
        """Write each validator row."""
        for identity_hash, power in self.validators.items():
            self.persistence.write_state("treasury_validators", identity_hash, power)

    def _persist_proposal(self, proposal: TreasuryProposal) -> None:
        """Write one proposal snapshot."""
        self.persistence.write_state(
            "treasury_proposals", proposal.proposal_id, proposal.to_mapping()
        )

    def _journal(self, event_type: str, payload: Mapping[str, object]) -> None:
        """Append an audit journal row."""
        self.persistence.append_journal("treasury", event_type, dict(payload))


def inference_commitment(prompt: str, output: str) -> str:
    """
    Compute the deterministic inference commitment verifiers re-execute.

    Args:
        prompt: Canonical prompt text.
        output: Canonical output text.

    Returns:
        SHA-256 hex of the canonical pair.
    """
    return sha256_hex(canonical({"prompt": prompt, "output": output}))


def build_proof(
    *,
    worker_identity_hash: str,
    prompt: str,
    output: str,
    verifier_identity_hashes: tuple[str, ...],
) -> ProofOfInference:
    """
    Build a well-formed Proof-of-Inference for a deterministic task.

    Args:
        worker_identity_hash: Worker validator.
        prompt: Prompt text.
        output: Claimed output.
        verifier_identity_hashes: Independent validators who re-executed the commitment.

    Returns:
        ProofOfInference ready for a MINT payload.
    """
    return ProofOfInference(
        request_hash=sha256_hex(prompt),
        result_hash=inference_commitment(prompt, output),
        worker_identity_hash=worker_identity_hash,
        prompt=prompt,
        output=output,
        verifier_identity_hashes=verifier_identity_hashes,
    )


def reject_contract_payload(payload: Mapping[str, object]) -> None:
    """
    Walk a proposal payload and reject smart-contract smuggling.

    Args:
        payload: Nested mapping that must remain data, never executable code.

    Returns:
        None
    """
    for key, value in _walk_items(payload):
        leaf_key = key.rsplit(".", 1)[-1].lower()
        if leaf_key in FORBIDDEN_CONTRACT_KEYS:
            raise TreasuryContractRejected(f"contract key forbidden: {leaf_key}")
        if isinstance(value, str):
            lowered = value.lower()
            for hint in FORBIDDEN_CONTRACT_PATTERN_HINTS:
                if hint in lowered:
                    raise TreasuryContractRejected(f"contract material: {hint}")


def _walk_items(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """Flatten mappings and lists into dotted paths."""
    found: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            found.append((path, inner))
            found.extend(_walk_items(inner, path))
        return found
    if isinstance(value, list):
        for index, inner in enumerate(value):
            path = f"{prefix}[{index}]"
            found.append((path, inner))
            found.extend(_walk_items(inner, path))
    return found


def _jsonable_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Copy a mapping into JSON-stable primitives."""
    return {str(key): _jsonable(inner) for key, inner in value.items()}


def _jsonable(value: object) -> object:
    """Convert schema-shaped proposal payloads into JSON-stable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _bootstrap_path() -> None:
    """Ensure repo root is importable when this file is executed directly."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if __name__ == "__main__":
    _bootstrap_path()
    raise SystemExit("SovereignTreasury is a library; run test/treasury/test_sovereign_treasury.py")
