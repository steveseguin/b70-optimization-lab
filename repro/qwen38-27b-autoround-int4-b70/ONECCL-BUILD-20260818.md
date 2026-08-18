# Two-B70 public oneCCL rebuild — 2026-08-18

Status: build, checksum gate, two-rank captured all-reduce oracle, and two-rank
captured all-gather oracle passed.

## Identity and build

- oneCCL parent: `b52f40c07f0b140e6aba87548c80720a350a9827`;
- `deps/libccl`: `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`;
- Intel oneAPI DPC++: `2025.3.3.20260319`;
- required source delta: only
  `oneccl-4ceafd1-intel-2025.3-build-compat.patch`;
- resulting `deps/libccl` tracked binary-diff SHA-256:
  `ce945209c5f9b67782a59eeb6b66da1a1d7c02532f08be1ee51f979b0508021b`;
- optional sequence-dependency experiment: disabled;
- build parallelism: one job;
- install root: `/home/steve/runtime/oneccl-4ceafd1-b70-public`.

```bash
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
source /opt/intel/oneapi/umf/1.0/env/vars.sh
set -u
export CMAKE_PREFIX_PATH=/opt/intel/oneapi/umf/1.0:/opt/intel/oneapi/compiler/2025.3
ONECCL_SOURCE_DIR=/home/steve/src/oneccl-public-qwen27 \
ONECCL_BUILD_DIR=/home/steve/src/oneccl-public-qwen27-build \
ONECCL_INSTALL_DIR=/home/steve/runtime/oneccl-4ceafd1-b70-public \
JOBS=1 APPLY_SEQUENCE_DEPENDENCY=0 \
  experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/build-public-oneccl.sh
```

The endpoint checksum gate is
[`manifests/oneccl-runtime-b52f40c-4ceafd1-oneapi2025.3.3-20260818.sha256`](manifests/oneccl-runtime-b52f40c-4ceafd1-oneapi2025.3.3-20260818.sha256).
The rebuilt `libccl.so.1.0` hash is host/compiler dependent; `kernels.spv`
matches the historical validated artifact byte for byte.

## Graph replay correctness

The exact Qwen target/verifier collective shape passed on both B70s:

- BF16 all-reduce `[4,5120]`, 512 command-graph replays per rank;
- `0/512` mismatch iterations on each rank;
- maximum absolute difference `0.0`;
- loaded library path was the rebuilt install on both ranks.

Evidence:
[`evidence/oneccl-allreduce-graph-20260818.json`](evidence/oneccl-allreduce-graph-20260818.json).

The intrinsic MTP draft collective also passed:

- BF16 blocking all-gather `[4,2560]`, 512 command-graph replays per rank;
- all 512 completed on each rank;
- zero mismatches and maximum absolute difference `0.0`;
- loaded library path was the rebuilt install on both ranks.

Evidence:
[`evidence/oneccl-allgather-graph-20260818.json`](evidence/oneccl-allgather-graph-20260818.json).

Both cards remained in `normal` state after the tests and the kernel journal
contained no new GPU reset, fault, hang, or panic entry.
