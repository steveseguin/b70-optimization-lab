# Closed attention state archival preparation

This fixed adapter reuses the exact verified filesystem `Job` from
[closed_baseline_bins.py](../closed_baseline_bins.py), SHA
`6a86c61fe46b453f7f9516d7b41169f0314cfc2b2716f82aab54b05c8df566ab`.
There is no new archive, unlink or offload implementation and no automatic phase
continuation. Preparation reads only repository audit indices. Actual operations
require the root coordinator's separate review and explicit invocation.

Two fixed authorities define eligible bytes:

| Profile | Closed groups | Files/group | Bytes/group |
|---|---:|---:|---:|
| `prefix` | fourteen measured arms, original prompts 0–6 | 2,108 | 221,743,168 |
| `completion` | initial state, two warmups, ten arms of prompts 7–11 | 2,113 | 231,442,500 |

Prefix authority is the immutable independent incomplete-run review 663fb5e4 and
its index 4f4e6ce9. It covers **only target-state files**, not all request auxiliary
buffers. Completion authority is review 068fe237 and index 1210bc4e, covering the
full closed evidence tree. The resulting 27 groups contain 56,981 eligible bins;
`plan.json` records every exact group and total. Every archived byte must match
its audited SHA before it becomes eligible for pruning.

All JSON, logs, directories and failure metadata stay at their original paths.
All unindexed prefix bins—including initial/warmup auxiliary files and the
failed prompt07-MTP partial state—stay untouched. No model, baseline or profile
root is accepted. The Q6 micro author confirmed its six fixtures come from
`gsq-profile-a`; that whole run is outside this helper's scope. Baseline's six
preserved micro files also remain outside scope. No candidate/completion fixture
was requested for preservation as of this preparation.

Run `--plan` for repository-only authority inspection. Actual phase arguments are
`--profile prefix|completion --batch N` with exactly one of `--archive`,
`--prune-verified`, `--offload-verified`, `--release-local-verified`. Prefix range is
0–13; completion range is 0–12. Each profile advances only after the preceding
batch's USB offload and local release are verified. Use nice19, helper cores
8–15,24–31 and the fixed Python environment. No phase automatically retries.

NVMe staging is fixed under
`/home/steve/own-xpu-runtime-results/gsq-attention-{profile}-bin-archive-a/chunk-NN`.
USB archives are fixed as
`/mnt/usb-models/own-xpu-runtime-results/gsq-attention-{profile}-state-bins-NN.tar.gz`.
Each copy has a 384MiB archive/stat quota,27GB plus64MiB reserve, full source
identity/SHA checks and full tar member readback. Prune re-verifies the held
archive and every original source before each unlink, after a durable restore
map. Offload and local release require the original source filesystem device,
distinct from NVMe, and retain 2GiB USB reserve. Local deletion follows complete
USB archive SHA/member verification. Partial failures retain evidence and stop.

For restoration, use the **profile's exact source root** in `archive-start.json`
and `prune-start.json`; tar names are paths relative to that root. The inherited
copy receipt's historical phrase “baseline root/index” means this bound profile
source/index, not the separate baseline directory. Verify all member digests
against the bound profile index before restoring missing files. Never overwrite
existing files without review. Archives contain original UID/GID/mode/mtime;
JSON and metadata were never deleted.

Keep the per-phase receipts, immutable independent indices, source recipe and
restore map permanently. Raw archives stay outside Git; their exact path and
SHA remain in offload receipts. No storage operation has been performed by the
preparation agent.
