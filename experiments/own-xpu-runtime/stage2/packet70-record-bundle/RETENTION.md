# Retained inputs and restoration

The executable is packet65's sealed `build/device/own-rt-iq3`, SHA-256
`8de8ec649cf378715cc6b59e358675a90c33ba2d104aa62a2d8100d41d0cf277`.
The 4 MiB rope table is a hash-checked reference to packet65, not another binary blob.
The host executable is also reused and never run during this preparation.
[Reuse manifest](binary-reuse.json) pins both paths, hashes and the copied
packet65 source bytes. No object files or large build trees were copied.
Selection binaries and byte fixtures are hardlinks; the main binary paths are
read-only references. Packet56 primitive fixtures and packet61's restored
input fixtures remain referenced or hardlinked under hash checks.

Ignored local links can be restored without compiling or running a model:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet70-record-bundle/restore_links.py </dev/null
```

This requires the pinned packet65 binaries and existing parent fixture tree.
If they are missing, restore their documented artifacts first. Packet65's
`RETENTION.md` owns its rebuild recipe. Packet70's `build-device-receipt.json`
is an unchanged copy of packet65's receipt, not a claim of a local compile.
The oracle is the same symlink to packet49; it must never be regenerated here.

The full input/write census is [input-checks.json.gz](evidence/input-checks.json.gz).
Compression was decompressed and byte-verified before the plain JSON was
removed. [Retention receipt](evidence/input-checks-retention.json) records both
hashes and the restore command. [Summary](evidence/input-summary.json) keeps
all window counts. Superseded preparation seals remain in `evidence/`; they
were never device-qualified. No historical sibling evidence was removed.

All device outputs go to the packet's registered external build directory.
The existing storage precheck still reserves the full chain and 8 GB free
floor. No model weights or raw device state are added to Git.
