# Qwen27 TP1 Persistent Worker Foundation

This directory is the Phase 1 control surface for four independent, persistent
single-B70 workers. It deliberately does not claim that llama.cpp currently
supports device-to-device restoration of KV/GDN state or dynamic kernel module
replacement. Those are later executor features.

The initial harness reuses the current llama.cpp binary, target GGUF, DFlash
GGUF, and server launcher. Keeping each server alive avoids repeated model
loads between ordinary endpoint screens. All four initial assignments use the
same MTP3 control profile so cross-card calibration precedes candidate work.
The DFlash GGUF profiles use `draft-simple`; they are available but are not
assigned by default.

Graph capture is requested so the launcher's explicit graph telemetry can
prove whether capture entered or was compatibility-rejected. A requested graph
is not counted as replay without the corresponding runtime evidence.

## Commands

Run non-mutating validation and status first:

```bash
python3 scripts/qwen27-tp1-workerctl.py validate
python3 scripts/qwen27-tp1-workerctl.py status
python3 scripts/qwen27-tp1-workerctl.py render
```

`start` and `stop` are dry runs unless `--execute` is supplied. A single worker
can be selected with `--worker`; omit it to address all four.

```bash
python3 scripts/qwen27-tp1-workerctl.py start --worker gpu0-baseline
python3 scripts/qwen27-tp1-workerctl.py start --worker gpu0-baseline --execute
python3 scripts/qwen27-tp1-workerctl.py status --json
python3 scripts/qwen27-tp1-workerctl.py stop --worker gpu0-baseline --execute
```

The controller refuses a start when its port is occupied, its managed PID is
live, or it detects another llama process explicitly pinned to that physical
GPU. A llama process with no explicit `ZE_AFFINITY_MASK` is conservatively
treated as a collision on every card. The controller never kills an unmanaged
process.

Runtime PID files, logs, and resolved worker identities live outside Git under
`/mnt/fast-ai/bench-results/qwen27-tp1-worker-harness/`.

## Evidence Boundary

- Persistent endpoint requests are development screens.
- Future golden activations and post-prefill snapshots are diagnostic-only.
- Neither is promotion evidence.
- Promotion must use the fixed cold realistic suite, unique first responses,
  disabled prompt/KV/history reuse, and `cached_tokens=0` for every request.

`model-pack-manifest.json` defines admission identity for the future offline
B70 pack without claiming that the native pack exists. The implemented first
artifact is a byte-identical shared-RAM GGUF cache:

```bash
python3 scripts/qwen27-model-cache.py status
python3 scripts/qwen27-model-cache.py prepare
python3 scripts/qwen27-model-cache.py verify
python3 scripts/qwen27-model-cache.py warm
python3 scripts/qwen27-model-cache.py drop        # dry run
python3 scripts/qwen27-model-cache.py drop --execute
```

Preparation streams and checks the source SHA-256 while atomically staging each
file under `/dev/shm`. Admission checks the source hash, cached hash, and exact
size. Each cache entry also records the llama.cpp commit/dirty-patch identity,
kernel and Intel userspace versions, tool revision, architecture, and layout.
Workers prefer an admitted entry and otherwise fall back to the original GGUF.
The files are mmap-compatible, and `warm` explicitly touches every host page.
Because `/dev/shm` is volatile, `prepare` is required after reboot; it currently
uses about 16 GiB of the 63 GiB mount. Never stage a second copy blindly.

This cache only shortens development initialization. It does not contain the
backend's reordered device weights and cannot improve decode throughput. The
current llama.cpp loader maps GGUF tensor offsets and performs the reorder into
GPU-only allocations; consuming a serialized reordered pack needs a new loader
ABI. The internal NVMe also had only 14 GiB free, less than the 16.06 GB target
GGUF, so a disk-native pack was not created unsafely.

`golden-corpus-manifest.json`
defines the required capture cases and marks every snapshot as ineligible for
headline or LocalMaxxing evidence.
