Prepare an evidence-bound PAN handoff.

1. Inspect the final diff and preserve unrelated changes (including untracked
   reference-code/ artifacts).
2. Run or clearly identify the applicable consumed-boundary validation.
   Default gate: `python test/run_pan_gate.py`.
3. Update STATE.md for runtime truth, MEMORY.md for durable findings,
   CONTEXT.md for retrieval links, NOTEPAD.md for active scratch, and
   security/AGENTS.md when the security surface changed, only when each
   surface's semantics changed.
4. Record the exact blocker and one imperative next action if incomplete.
   Current next action is the real `_run_inference` owner (finish-prior).
   qemu-img / qemu-system-x86_64 plus an Android image is later, not
   co-equal. Do not list prompt_bridge as next work. Do not expand
   master_db §6.2.
5. Regenerate filetree.md with FileTree Pro if the repository structure
   changed; never hand-edit it.
