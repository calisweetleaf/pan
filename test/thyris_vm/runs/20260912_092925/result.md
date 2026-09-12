# Thyris VM owners run 20260912_092925

I ran `python test/thyris_vm/test_thyris_vm.py` at 20260912_092925.
I found status `fail` with 6 passed, 1 failed, 0 skipped.

## What I required

I required phone_orchestrator to import against live memory/ and telecom/
owners, VMImageManager and VMSupervisor to construct on tempdirs, AIPC
prompt_bridge to be unbound from the Thyris seam, USMS/Erebus to own
cognition without prompt_bridge, host-tool fail-loud to name qemu/adb,
and ISOConverter._create_disk to write a real qcow2 when qemu-img exists.
This consumer does not boot a guest and does not claim Android images.

## Checks

- `phone_orchestrator_imports`: pass
- `image_manager_constructs`: pass
- `supervisor_constructs`: pass
- `aipc_prompt_unbound`: pass
- `usms_erebus_has_no_prompt`: pass
- `telecom_host_tools_contract`: pass
- `qemu_img_disk_create`: fail
  - error: `CheckFailure: qemu-img missing; disk-create is unproven`

## Artifacts

- `/workspace/test/thyris_vm/runs/20260912_092925/result.json`
- `/workspace/test/thyris_vm/runs/20260912_092925/result.md`
- `/workspace/test/thyris_vm/runs/20260912_092925/result.log`

