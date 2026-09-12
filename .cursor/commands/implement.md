Execute one bounded PAN implementation unit under root AGENTS.md and the
applicable scoped rules.

Before editing production Python, create or update root SCOPE.md with the
Somnus Code Forge engagement mode and direct-edit justification. Prefer EDIT for
owned PAN code. Do not introduce a wrapper, shim, or parallel package unless the
source owner and durable external adaptation boundary are explicit.

Work at the owning seam:

- Nation pillars: PAN_SDK/treasury.py, PAN_SDK/email_social.py,
  PAN_SDK/master_db.py
- Immune / Erebus: security/planetary_immune_system.py +
  security/sovereign_firewall.py + memory/unified_memory_system.py
- Thyris telecom: telecom/vm_supervisor.py, telecom/vm_image_manager.py,
  telecom/phone_orchestrator.py
- Thyris VM memory: memory/memory_core.py, memory/system_cache.py

Do not create memory_system. Do not pull or dummy core.prompt_bridge. Thyris is
telecommunications, not AIPC. Phones do not contain in-device AI.

Inspect the real consumer first. Make the smallest complete direct integration,
run the narrowest meaningful consumer test, widen validation as justified, and
report baseline failures separately from regressions. Update persistent state
only where its semantic owner changed.

The next justified production unit is a real SovereignInferenceEngine._run_inference
owner in PAN_SDK/PAN_SDK.py (finish-prior; decision packet first, then EDIT in a
new SCOPE.md). Treasury verify_proof_of_inference must eventually call that
owner. Do not dummy the engine. Do not start a qemu/Android unit. Do not expand
master_db §6.2. Do not start a prompt_bridge unit. qemu host tools remain a
later frontier after the inference owner is selected and landed.
