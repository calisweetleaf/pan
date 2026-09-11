Verify the active PAN change at its consumed boundary.

Run the narrowest relevant test or scenario first. Direct Python only; no pytest.
Each consumer must print a detailed terminal readout and write JSON + Markdown
artifacts.

Project gate (latest verified Windows command, `.venv` Python 3.14):

    python test/run_pan_gate.py

POSIX spelling: `python3 test/run_pan_gate.py`.

Focused consumers:

    python test/test_pan_persistence.py
    python test/probe_name_registry.py
    python test/test_pan_manifest.py
    python test/probe_personal_data.py
    python test/pan_sdk_system_scenario.py
    python test/immune/test_planetary_immune_system.py
    python test/treasury/test_sovereign_treasury.py
    python test/email_social/test_email_social.py
    python test/master_db/test_master_db.py
    python test/memory_core/test_memory_core.py
    python test/thyris_vm/test_thyris_vm.py

For a production Python promotion, apply the Somnus Code Forge verification
lane, real fixtures, run artifacts, and SOTA_RUN.md ledger requirements. Then
run the gate when baseline state permits.

Report:

- exact commands and exit status;
- passed, failed, and not-run checks;
- whether a failure predates the change;
- what the evidence proves and does not prove (import is not QEMU boot;
  green gate is not `_run_inference`).

Do not mutate assertions, add skips, or claim success from structural evidence.
Do not treat a missing core.prompt_bridge as a failing Thyris check.
