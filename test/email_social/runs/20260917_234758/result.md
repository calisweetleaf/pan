# Email/social overlay run 20260917_234758

I ran `python test/email_social/test_email_social.py` at 20260917_234758.
I found status `pass` with 5 passed, 0 failed, 0 skipped.

## What I required

I required identity-hash addressing, hybrid sealed mail, blind dual relays,
firewall inspection, IP rejection, and sqlite hydrate after reopen.

## Checks

- `sealed_mail_across_relays`: pass
- `legacy_ip_rejected`: pass
- `relay_blocks_unsigned_and_routing`: pass
- `social_and_knock`: pass
- `restart_hydrates_relay`: pass

## Artifacts

- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/email_social/runs/20260917_234758/result.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/email_social/runs/20260917_234758/result.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/email_social/runs/20260917_234758/result.log`

