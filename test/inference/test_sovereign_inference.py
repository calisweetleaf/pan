"""Direct consumer for SovereignInferenceEngine._run_inference.

Real tempdir model files. No mocks. JSON+MD+LOG artifacts.
"""

from __future__ import annotations

import io
import json
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

from PAN_SDK import SovereignCommunicator, SovereignIdentity
from PAN_SDK.PAN_SDK import (
    InferenceError,
    InferenceModelError,
    ModelManifest,
    SovereignInferenceEngine,
    write_linear_model,
)


DUMMY_MARKERS = (
    "Simulated response to:",
    "processed with proprietary quantization",
    "Enhanced response to:",
    "enhanced quantization v2.0",
)


class CheckFailure(Exception):
    """A named inference check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _engine_for(tmpdir: str, *, seed: bytes, name: str) -> SovereignInferenceEngine:
    """Write a real PANLIN01 file and return a matching engine."""
    model_path = Path(tmpdir) / f"{name}.panlin"
    model_hash = write_linear_model(model_path, seed=seed)
    creator = SovereignIdentity(f"{name}-creator")
    model_identity = SovereignIdentity(f"{name}-model")
    manifest = ModelManifest(
        model_name=name,
        model_hash=model_hash,
        model_public_key_pem=model_identity.get_public_key_pem(),
        creator_identity=creator,
    )
    engine = SovereignInferenceEngine(str(model_path), manifest)
    engine.load_model()
    print(f"loaded {name} hash={model_hash[:12]} bytes={model_path.stat().st_size}")
    return engine


def _reject_dummy(text: str, label: str) -> None:
    """Fail if the old canned strings leak through."""
    for marker in DUMMY_MARKERS:
        if marker in text:
            raise CheckFailure(f"{label} still contains dummy marker: {marker}")


def check_missing_model_fails_loud(details: dict[str, object]) -> None:
    """load_model raises when the weight file is absent."""
    with tempfile.TemporaryDirectory(prefix="infer_missing_") as tmpdir:
        creator = SovereignIdentity("MissingCreator")
        model_identity = SovereignIdentity("MissingModel")
        missing = Path(tmpdir) / "absent.panlin"
        manifest = ModelManifest(
            model_name="absent",
            model_hash="0" * 64,
            model_public_key_pem=model_identity.get_public_key_pem(),
            creator_identity=creator,
        )
        engine = SovereignInferenceEngine(str(missing), manifest)
        try:
            engine.load_model()
            raise CheckFailure("missing model file was accepted")
        except InferenceModelError as exc:
            print(f"missing model failed loud: {exc}")
            details["error"] = str(exc)
            if "missing" not in str(exc).lower():
                raise CheckFailure("missing-file error did not name the gap")


def check_hash_mismatch_fails_loud(details: dict[str, object]) -> None:
    """Manifest hash must equal the file SHA-256."""
    with tempfile.TemporaryDirectory(prefix="infer_hash_") as tmpdir:
        model_path = Path(tmpdir) / "mismatch.panlin"
        write_linear_model(model_path, seed=b"pan-hash-mismatch")
        creator = SovereignIdentity("HashCreator")
        model_identity = SovereignIdentity("HashModel")
        manifest = ModelManifest(
            model_name="mismatch",
            model_hash="deadbeef" * 8,
            model_public_key_pem=model_identity.get_public_key_pem(),
            creator_identity=creator,
        )
        engine = SovereignInferenceEngine(str(model_path), manifest)
        try:
            engine.load_model()
            raise CheckFailure("hash mismatch was accepted")
        except InferenceModelError as exc:
            print(f"hash mismatch failed loud: {exc}")
            details["error"] = str(exc)


def check_corrupt_header_fails_loud(details: dict[str, object]) -> None:
    """Non-PANLIN01 bytes are rejected."""
    with tempfile.TemporaryDirectory(prefix="infer_hdr_") as tmpdir:
        model_path = Path(tmpdir) / "junk.panlin"
        model_path.write_bytes(b"not-a-model")
        creator = SovereignIdentity("JunkCreator")
        model_identity = SovereignIdentity("JunkModel")
        manifest = ModelManifest(
            model_name="junk",
            model_hash="ab" * 32,
            model_public_key_pem=model_identity.get_public_key_pem(),
            creator_identity=creator,
        )
        engine = SovereignInferenceEngine(str(model_path), manifest)
        try:
            engine.load_model()
            raise CheckFailure("corrupt header was accepted")
        except InferenceModelError as exc:
            print(f"corrupt header failed loud: {exc}")
            details["error"] = str(exc)


def check_reexecution_matches(details: dict[str, object]) -> None:
    """Two engines on the same file emit the identical decode."""
    with tempfile.TemporaryDirectory(prefix="infer_replay_") as tmpdir:
        first = _engine_for(tmpdir, seed=b"pan-replay-linear", name="replay")
        prompt = "infer:civic-cycle-1"
        once = first.infer(prompt, temperature=0.0, max_tokens=24)
        twice = first._run_inference(prompt, 0.0, 24)
        second = SovereignInferenceEngine(first.model_path, first.model_manifest)
        second.load_model()
        peer = second.infer(prompt, max_tokens=24, temperature_milli=0)
        print(f"output_len={len(once)} once==twice={once == twice} once==peer={once == peer}")
        _reject_dummy(once, "replay output")
        if once != twice:
            raise CheckFailure("infer and _run_inference diverged")
        if once != peer:
            raise CheckFailure("peer engine diverged from the worker")
        details["output_len"] = len(once)
        details["model_hash"] = first.model_manifest.model_hash
        details["matched"] = True


def check_prompt_and_temperature_diverge(details: dict[str, object]) -> None:
    """Different prompts and temperatures are not a constant dummy string."""
    with tempfile.TemporaryDirectory(prefix="infer_div_") as tmpdir:
        engine = _engine_for(tmpdir, seed=b"pan-diverge-linear", name="diverge")
        civic = engine.infer("infer:civic-cycle-1", max_tokens=24, temperature_milli=0)
        reserve = engine.infer("infer:reserve-fill", max_tokens=24, temperature_milli=0)
        hot = engine.infer("infer:civic-cycle-1", max_tokens=24, temperature_milli=4000)
        _reject_dummy(civic, "civic")
        _reject_dummy(reserve, "reserve")
        _reject_dummy(hot, "hot")
        print(
            f"civic_len={len(civic)} reserve_len={len(reserve)} "
            f"civic==reserve={civic == reserve} civic==hot={civic == hot}"
        )
        if civic == reserve:
            raise CheckFailure("two distinct prompts produced the same output")
        if civic == hot:
            raise CheckFailure("temperature_milli did not change the decode")
        details["civic_len"] = len(civic)
        details["diverged_prompt"] = True
        details["diverged_temperature"] = True


def check_process_request_uses_owner(details: dict[str, object]) -> None:
    """Packet path calls the same owner as infer."""
    with tempfile.TemporaryDirectory(prefix="infer_pkt_") as tmpdir:
        engine = _engine_for(tmpdir, seed=b"pan-packet-linear", name="packet")
        user = SovereignIdentity("PacketUser")
        communicator = SovereignCommunicator(user)
        prompt = "Explain sovereign inference replay"
        packet = communicator.create_packet(
            "INFERENCE_REQUEST",
            {"prompt": prompt, "temperature": 0.0, "max_tokens": 20},
        )
        response = engine.process_request(packet, user.get_public_key_pem())
        direct = engine.infer(prompt, max_tokens=20, temperature_milli=0)
        text = str(response.content.get("response") or "")
        print(
            f"kind={response.kind} parent={response.parents} "
            f"packet==infer={text == direct} model_hash={response.content.get('model_hash', '')[:12]}"
        )
        _reject_dummy(text, "packet response")
        if response.kind != "INFERENCE_RESPONSE":
            raise CheckFailure("response kind is not INFERENCE_RESPONSE")
        if not response.parents or response.parents[0] != packet.packet_id:
            raise CheckFailure("response is not linked to the request")
        if text != direct:
            raise CheckFailure("process_request diverged from infer")
        if response.content.get("model_hash") != engine.model_manifest.model_hash:
            raise CheckFailure("response omitted the verified model_hash")
        details["response_len"] = len(text)
        details["processing_time_ms"] = response.content.get("processing_time_ms")
        details["matched_infer"] = True


def check_illegal_args_fail_loud(details: dict[str, object]) -> None:
    """max_tokens and temperature reject illegal values."""
    with tempfile.TemporaryDirectory(prefix="infer_args_") as tmpdir:
        engine = _engine_for(tmpdir, seed=b"pan-args-linear", name="args")
        try:
            engine.infer("ok", max_tokens=0)
            raise CheckFailure("max_tokens=0 was accepted")
        except InferenceError as exc:
            print(f"max_tokens=0 failed loud: {exc}")
        try:
            engine.infer("ok", temperature=-1.0)
            raise CheckFailure("negative temperature was accepted")
        except InferenceError as exc:
            print(f"negative temperature failed loud: {exc}")
            details["temperature_error"] = str(exc)


CHECKS = (
    ("missing_model_fails_loud", check_missing_model_fails_loud),
    ("hash_mismatch_fails_loud", check_hash_mismatch_fails_loud),
    ("corrupt_header_fails_loud", check_corrupt_header_fails_loud),
    ("reexecution_matches", check_reexecution_matches),
    ("prompt_and_temperature_diverge", check_prompt_and_temperature_diverge),
    ("process_request_uses_owner", check_process_request_uses_owner),
    ("illegal_args_fail_loud", check_illegal_args_fail_loud),
)


def run() -> dict[str, object]:
    """Execute every inference check and return a gate-shaped payload."""
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
            InferenceError,
            InferenceModelError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
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
        "name": "sovereign_inference",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} inference checks failed"
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
        f"# Sovereign inference run {timestamp}",
        "",
        f"I ran `python test/inference/test_sovereign_inference.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required a real on-disk PANLIN01 weight file, fail-loud load on missing",
        "or mismatched bytes, bit-identical re-execution by a second engine, prompt",
        "and temperature divergence, and process_request to call that same owner.",
        "I rejected the old canned simulation strings.",
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
        print(f"inference consumer start {timestamp}")
        payload = run()
        print(f"inference consumer status={payload.get('status')}")
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
