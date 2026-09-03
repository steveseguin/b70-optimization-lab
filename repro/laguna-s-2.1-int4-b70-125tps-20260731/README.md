# Reproduce the exact Laguna S 2.1 125.462 tok/s four-B70 record

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

This packet reproduces the current BF16-KV record configuration. It does not
claim that a source rebuild will have byte-identical native binaries; rebuilt
artifacts are a new environment and must pass the complete gate.

## Result and identity

- conventional median: `125.4619731637751 tok/s`;
- historical compatibility: `126.72926582199506 tok/s`;
- target: `poolside/Laguna-S-2.1-INT4` revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft: `poolside/Laguna-S-2.1-DFlash-INT4` revision
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM: `1a7f61feffbc61b21b73f812d231c7426386ccdc`;
- XPU kernels: `99886d783372e621941228250091dc8ebdc1595d`;
- candidate `_C.abi3.so`:
  `36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095`;
- runtime lock:
  `64b0f04d29aabcabd65c0f71ff6a4c0923208228abd0559f2308e63fb3334829`;
- BF16 KV, TP4+EP4, exact M12 verifier, DFlash11, one active generation.

The sealed originating-host run is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-shared-elementwise-m12-formal-20260801T053000Z
```

Its benchmark, exactness, identity, server log, runtime verification, status,
and pre/post idle evidence are authoritative. Checksums are in
[`data/laguna-shared-elementwise-m12-record-20260731.json`](../../data/laguna-shared-elementwise-m12-record-20260731.json).

## Restore source

Complete-history bundles:

- `patches/laguna-s-2.1-xpu-b70/vllm-laguna-shared-elementwise-m12-1a7f61fef-20260731.bundle`;
- `patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-shared-elementwise-m12-99886d783-20260731.bundle`.

Reviewable patch series:

- `0001-xpu-add-exact-Laguna-M12-shared-elementwise-ops.patch`;
- `0001-xpu-enable-exact-Laguna-M12-shared-elementwise-ops.patch`;
- `0002-xpu-preserve-Laguna-MoE-layer-prefixes.patch`;
- `0003-xpu-emit-Laguna-selector-evidence-per-worker.patch`.

Verify each bundle with `git bundle verify`, fetch its experiment branch into
the matching upstream repository, and check out the exact commit above. A
focused `_C` build used oneAPI 2025.3.3; every other native module and mapped
DSO was copied byte-for-byte from the prior QKNorm/RoPE record and is pinned by
`runtime-lock-shared-elementwise-m12.json`.

## Run

On the originating host, with the exact source worktrees and binary hashes in
place:

```bash
cd /path/to/b70-optimization-lab
repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh
```

The gate defaults to the originating host's layout. Each variable below may
point at the same verified artifacts elsewhere; when a default is absent the
gate stops with a message naming the variable instead of creating a path:

- `REPRO_VLLM_TREE`: clean vLLM checkout at `1a7f61fef` restored from the
  bundle;
- `REPRO_KERNEL_TREE`: clean XPU-kernel checkout at `99886d783` restored from
  the bundle, carrying the lock-pinned native modules in `vllm_xpu_kernels/`;
- `REPRO_VENV_ROOT` and `REPRO_XPUMEM_MODULE`: the pinned virtual environment
  and `xpumem_allocator.abi3.so` described in the
  [102 tok/s packet](../laguna-s-2.1-int4-b70-102tps-20260726/README.md);
- `REPRO_MODEL_ROOT`: the verified `int4/` and `dflash-int4/` payloads plus
  the `.verification/` manifests (see `restore-models.sh` in that packet);
- `REPRO_ARTIFACT_ROOT`: a local NVMe root that receives
  `runs/<timestamped run directory>`;
- `REPRO_NVME_DEVICE` and `REPRO_NVME_FSTYPE`: the block device and
  filesystem the model and artifact roots must be mounted from.

The canonical q1 teacher that the exactness contract compares against is
tracked here as `teacher-q1-canonical-bench.json` (SHA-256
`d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1`), so no
originating-host run directory is needed for it.

The script invokes the fail-closed formal launcher. It hashes the full model,
verifies source and every native origin, requires an idle host, sends each of
13 unique prompts once, compares token IDs and text hashes to canonical q1,
requires cache-zero, four-rank 146/145 target and 14/13 draft topology, four
selector markers, 72-second pre/post idle, and clean teardown. It performs no
warmup or retry. The first valid result is the result.

Read the [record note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md)
and [preregistration chronology](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-preregistration.md)
before changing any identity field.
