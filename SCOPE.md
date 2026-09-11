# SCOPE — closed: AIPC prompt_bridge unbound from Thyris telecom

**Status:** CLOSED 2026-09-11. Not the active unit.
**Ledger:** SOTA_RUN.md (unbind run)
**Snapshot:** snapshots/v0.7/manifest.json
**Gate:** results/pan_gate_20260911_011502.json

The next production unit is not declared here. Next justified action (STATE.md):
prove `qemu-img` / `qemu-system-x86_64` plus an Android image on a real
disk-create consumer, or implement the real `SovereignInferenceEngine._run_inference`
owner. Do not pull `core.prompt_bridge`. Do not dummy either gap.

## Closed engagement (historical)

- mode: EDIT
- target_module: telecom/vm_supervisor.py
- target_module_provenance: operator-pulled Thyris VM supervisor (AIPC-era prompt hook still present)
- justification: I edited the owned telecom supervisor in place because wrapping a missing core.prompt_bridge would invent a prompt layer Daeron rejected. Thyris is telecommunications; phones do not contain in-device AI. The AIPC PromptSystemBridge hook is not a Thyris import or lifecycle requirement. USMS/Erebus already bind Ed25519 memory to RSA PAN packets and do not consume prompt_bridge.
- author: daeron
- date: 2026-09-11
- closed: 2026-09-11 after gate 20260911_011502

## Targets (closed)

| Target | Owner | Consumed boundary |
|---|---|---|
| `telecom/vm_supervisor.py` | VMSupervisor, CustomVMManager, CustomNetworkManager | Thyris VM lifecycle without PromptSystemBridge |
| `telecom/phone_orchestrator.py` | ThyrisPhoneOrchestrator | phone/packet orchestration; host tools qemu-img/qemu-system/adb |
| `test/thyris_vm/test_thyris_vm.py` | Thyris VM consumer | prove prompt unbound; prove USMS has no prompt_bridge; host-tool contract |
| `test/run_pan_gate.py` | project gate | re-run after unbind |

## Direct-edit justification

The prompt loader lived inside the owning supervisor. A wrapper or a new `core/` package would have reintroduced the AIPC dependency Daeron forbade. Removing `_load_prompt_bridge` and the in-VM prompt methods was a contract repair, not a new domain.

## Still out of scope until a new SCOPE is opened

- Do not create `core/` or dummy `PromptSystemBridge`
- Do not invent an Erebus prompt layer
- Do not collapse USMS into `memory.memory_core`
- Do not dummy `schemas.session`
- Do not claim QEMU/Android phones boot
- Agnostic `_run_inference`; Orama / vector spaces
