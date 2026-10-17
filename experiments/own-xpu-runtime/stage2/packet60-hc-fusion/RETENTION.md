# Compiler-input snapshot retention

The parent build directory is a symlink into the external results store. The
screen seal correctly rejects repository source entries that escape through
that symlink. Packet60 retains 172 byte-identical compiler-input snapshots
(13,896,576 bytes total) and records their original paths and SHA256 values in
[the build receipt](build-device-receipt.json). The build rehashes the originals
before compilation and both original/copy after linking. These are retained
source evidence, not disposable compiler caches. Runtime code is linked into
the sealed binary; runtime RoPE and draft-manifest files are separately bound.

One retained input exceeds the repository's 1 MiB review threshold:

- Path: `evidence/inherited-build-inputs/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet45-merged3/build/fusion-rope.hpp`.
- Size: 12,583,129 bytes.
- Purpose/consumer: packet45's generated RoPE fixture header is part of the
  unchanged packet56 checked compiler closure and inherited fixture object
  linked into this engine. It is retained verbatim to close the exact build
  identity; this task does not prune or change those inherited link inputs.
- Retention: keep while this screen seal or its build receipt is consumed.
  Duplicate content does not authorize removal.
- Restoration: recover these exact tracked bytes from this packet's Git commit,
  or restore the original compiler input identified by the build receipt and
  require the recorded SHA256 before recreating the snapshot. `build_engine.py`
  performs that verification and copy for an unsealed reconstruction.

The ignored `build/` is about 96 MB, recreated with `build_engine.py` followed
by `cpu_gate.py`; the parent checked inputs must first be restored. Keep this
built instance intact until the coordinator finishes its screen. No model
weights or payloads are included in these snapshots.
