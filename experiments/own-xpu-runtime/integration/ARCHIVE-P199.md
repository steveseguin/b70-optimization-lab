# Closed packet199 checkpoint retention

The two surviving packet199 states are closed evidence from the passed six-turn
HTTP experiment and restore28. These additive helpers preserve them in one
uncompressed external tar before a separate, explicit removal of local tensor
copies. The original packet199 manifests, checkers and result receipts stay
unchanged.

The fixed scope is `p199-a-7c4609adccb5044b2ca331a8` and
`p199-fresh-11d2d955e66fc33761c0328e` under packet199's
`evidence/runcheckpoints`. The archive contains all 262 files (147,737,106 bytes)
with safe relative names rooted at `checkpoints/`. Each manifest declares 128
native blobs plus token history, so all 129 binary digests per tree are checked.
Only the 242 untracked `blk.*.bin` tensor copies are prune candidates, totaling
146,964,480 bytes. All four metadata files, 16 small binary files, and existing
native lock siblings remain local.

`archive_p199_checkpoints.py` reuses only the hash/stamp primitives from the
exact-pinned committed p184 helper. `--plan` reads metadata, pinned closure
receipts, tracked status and the single destination mount's identity/headroom;
it explicitly does not claim to have rehashed tensor payloads. No services or
native executables run during planning.

`--copy-verify` requires the historical p199 owner/window units inactive, its
recorded owner PID absent, and both existing native lockfiles exclusively locked
without waiting. It holds those locks across complete original hashing, tar
creation, full member readback and original rehash. It refuses existing output
paths, writes an archive SHA256 sidecar, and retains failures for review. The
fixed target is
`/mnt/usb-models/own-runtime-archives/p199-closed-checkpoints-20261023.tar`.
The archive filesystem UUID, device, and parent inode are checked; no external
tree scan, mount change or model-file access occurs.

`prune_p199_checkpoints.py` is separate. It rechecks the exact successful copy
receipt, all originals/native digests, source/closure pins, tracked status, full
archive members and archive SHA. It retains the verified archive FD and native
lock FDs through deletion, rechecking their identities before every unlink.
Before removing any tensor, it writes an incomplete-local marker and full
restoration map **outside** the checkpoint directories. A partial failure still
leaves that recovery pointer. It never removes tracked files, metadata or small
control/token files, and never retries automatically.

The root coordinator executes these commands only after source review; the
preparation agent has not copied, archived or pruned the real checkpoints:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/integration/archive_p199_checkpoints.py --plan
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/integration/archive_p199_checkpoints.py --copy-verify
# Separate decision after reviewing the verified-copy-only receipt:
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/integration/prune_p199_checkpoints.py --prune-verified-copies
```

The archive and prune receipts are `checkpoint-archive-20261023.json` and
`checkpoint-local-prune-20261023.json` under packet199 `evidence`; the marker is
`ARCHIVED-CHECKPOINTS-20261023.json` beside them. Restoration first verifies the
whole archive and every member against the archive receipt, then reconstructs
both complete trees in a fresh private destination using `restore_map`. Do not
run native inspect/restore against the deliberately incomplete local trees.

Nine focused CPU tests use tiny synthetic files, in-memory tar members and
intercepted unlink/host calls. They cover native digest/file-set mismatch,
duplicate/foreign/corrupt archive members, retained archive FD replacement,
fresh-output refusal, required verified-copy proof and the marker preceding the
first unlink, plus a final archive-check refusal staying failed in its receipt.
They perform no real archive/copy/prune or service/device action.
This storage operation does not change any serving qualification or throughput
claim. The expected recovery adds about 147 MB to packet200's forecast margin;
the 27 GB floor and separate 768 MiB + 1 MiB reserves remain unchanged.

Every JSON write fsyncs its contents and parent directory. Tar and SHA sidecar
creation likewise fsync their parent directory before success is published.
The incomplete-local marker's directory fsync must succeed before the first
unlink; unsupported or failed directory fsync is a hard refusal. Three added
CPU fixtures verify file-then-directory ordering, error propagation, and no
deletion when marker durability fails (12 tests total). The prior nine-test
review and exact sources are preserved under
`lineage/p199-archive-before-directory-fsync/`.
