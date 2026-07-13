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

`model-pack-manifest.json` defines admission identity for the offline B70
packs. The first implemented artifact was a byte-identical shared-RAM GGUF
cache:

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

That RAM cache only shortens development initialization. It does not contain the
backend's reordered device weights and cannot improve decode throughput. The
current llama.cpp loader maps GGUF tensor offsets and performs the reorder into
GPU-only allocations; consuming a serialized reordered pack needs a new loader
ABI. The internal NVMe also had only 14 GiB free, less than the 16.06 GB target
GGUF, so the later 6.07 GiB native M6 pack set was placed on the external model
disk rather than consuming the remaining system NVMe space.

`golden-corpus-manifest.json`
defines the required capture cases and marks every snapshot as ineligible for
headline or LocalMaxxing evidence.

## Reusable Kernel Iteration Artifacts

`scripts/qwen27-iteration-artifacts.py` turns the iteration manifests into
checked artifacts while preserving the evidence boundary:

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
python3 scripts/qwen27-iteration-artifacts.py fingerprint
python3 scripts/qwen27-iteration-artifacts.py golden-prepare
python3 scripts/qwen27-iteration-artifacts.py golden-verify
python3 scripts/qwen27-iteration-artifacts.py focused --gpu 0
python3 scripts/qwen27-iteration-artifacts.py focused --gpu 0 --reuse-pass
```

The golden set contains deterministic packed Q4_0 weights, packed Q8_1 inputs,
and FP32 reference outputs at `M=1/4/8/16`, with representative `K=5120`.
Each tensor has an independent SHA-256. These are synthetic kernel-contract
fixtures, not claimed model activations. Real QKV/GDN/KV and commit/rollback
captures remain outstanding and are still listed in the corpus manifest.

The focused runner first verifies every golden tensor, then runs the current
Q4_0 reorder and fused-boundary backend tests. Its result key includes the
runtime commit/dirty-patch hash, CMake cache, binary checksums, Intel userspace,
GPU assignment, selected tests, and explicit environment overrides. A prior
pass is only reused when `--reuse-pass` is requested and that exact key exists.
Ordinary invocations always execute the tests.

An offline pack emitted by any current or future packer can be admitted without
copying the large payload:

```bash
python3 scripts/qwen27-iteration-artifacts.py pack-register \
  --pack-artifact /outside/git/path/to/pack \
  --packer-revision PACKER_COMMIT \
  --layout LAYOUT_NAME \
  --kernel-abi ABI_NAME
python3 scripts/qwen27-iteration-artifacts.py pack-verify --pack-key KEY
```

The registry hashes every file and keys the admission by source-model hash,
packer revision, layout, and aggregate artifact hash. It does not pretend the
current llama.cpp loader can bind serialized SYCL-reordered device weights:
that loader ABI is still required. The existing byte-identical GGUF RAM cache
remains the safe way to accelerate model initialization today.

## Native Xe2 M6 Pack Cache

The 130 Q4_0 gate/up tensors used by the guarded width-6 Xe2 experiment now
have a real persistent disk artifact in the exact `q4_0-xe2-dpas-v2` layout:

```bash
python3 scripts/qwen27-xe2-m6-pack-cache.py inspect
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/qwen27-xe2-m6-pack-cache.py prepare
python3 scripts/qwen27-xe2-m6-pack-cache.py verify --deep
python3 scripts/qwen27-xe2-m6-pack-cache.py stage-ram
python3 scripts/qwen27-xe2-m6-pack-cache.py stage-validate
```

The set and every tensor are content-addressed by the target model SHA-256,
tensor name/shape/type, layout version, and `bmg-g31`. Each tensor manifest
records both source-tensor and packed-payload SHA-256 values. `verify` performs
a fast key/size admission; `verify --deep` rehashes all 6.07 GiB before loader
use. `prepare --skip-source-hash` is a fast development-only lookup when the
already-recorded model checksum is trusted; it is not a replacement for first
admission or deep verification.

The cache is stored outside Git under `/mnt/usb-models/model-packs/`. A future
llama.cpp loader can mmap the admitted payloads, but protected llama.cpp source
was not changed by this tooling work. Measurements and the exact artifact key
are in
[`../notes/2026-07-13-xe2-m6-persistent-pack-cache.md`](../notes/2026-07-13-xe2-m6-persistent-pack-cache.md).

`stage-ram` establishes one durable deep-validation receipt when needed, then
atomically publishes the 130 payloads below `/dev/shm/qwen27-xe2-m6-v2/`.
Subsequent `stage-ram` or `stage-validate` calls trust the unchanged manifest,
receipt, canonical keys, exact file sizes, and the disk files' stat-identity
table, avoiding another 6.07 GiB hash pass while still invalidating trust when
an artifact is replaced or modified. `stage-validate --deep` remains available
for an explicit RAM checksum. The stage refuses to consume the last 8 GiB of
`/dev/shm` by default.
