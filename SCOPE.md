# SCOPE — Thyris owners into PAN memory/ and telecom/

## Engagement Mode

- mode: EDIT
- target_module: memory/memory_core.py
- target_module_provenance: operator-pulled Thyris VM memory (not USMS)
- justification: I am editing the pulled owners in place so telecom/phone_orchestrator.py can import MemoryManager, SomnusCache, VMSupervisor, and VMImageManager from this repository's existing memory/ and telecom/ packages. A memory_system package or wrapper would duplicate the join and collapse Thyris VM memory into USMS. Dummy prompt-bridge classes are rejected; missing core.prompt_bridge stays fail-loud.
- author: daeron
- date: 2026-09-11

## Targets

| Target | Owner | Consumed boundary |
|---|---|---|
| `memory/memory_core.py` | MemoryManager, MemoryConfiguration | Thyris VM session memory; tempdir sqlite + local embeddings |
| `memory/system_cache.py` | SomnusCache | runtime cache over MemoryManager |
| `memory/__init__.py` | package exports | USMS and Thyris symbols coexist; no identity collapse |
| `telecom/vm_supervisor.py` | VMSupervisor, CustomVMManager, CustomNetworkManager, VMState, ResourceProfile | phone_orchestrator already imports these names |
| `telecom/vm_image_manager.py` | VMImageManager, OSFamily | VMSupervisor image owner |
| `telecom/phone_orchestrator.py` | ThyrisPhoneOrchestrator | `memory.memory_core` / `memory.system_cache` instead of `memory_system.*` |
| `test/run_pan_gate.py` | project gate | compile + import phone_orchestrator after owners exist |

## Direct-edit justification

The four files already sit at the owning seams. Changing import paths and removing in-module dummy MemoryManager/SomnusCache/PromptSystemBridge classes is a contract repair, not a new domain. Wrapping them would create a second memory package, which the operator forbade.

## Out of scope this unit

- Do not create a `memory_system` package
- Do not collapse, wrap, or replace `memory/unified_memory_system.py`
- Do not dummy `core.prompt_bridge`, `schemas.session`, or `thyris.virtual_machine`
- Do not claim QEMU VMs boot, Android images install, or sentence-transformers models download
- `memory/memory_integration.py` remains unconsumed: it still needs `schemas.session`
- Agnostic `_run_inference`; Orama / vector spaces
