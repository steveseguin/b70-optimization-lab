# Qwen3.8 Flash-Next BF16 dense-invariance Phase 1

Date: 2026-09-02

Status: frozen before XPU execution; CPU-only contracts pass

## Question and correction

This bounded component census asks whether the real BF16 dense projections in
the active Qwen3.8 Flash-Next FP8 TP4 target path preserve exact per-row bytes
when M, row order, repeated invocation, and process identity change.

The first design incorrectly described A28 as 13 shapes. Re-running the frozen
A28 trace summarizer with a larger display limit exposed two one-call shapes
that its top-25 table omitted. The complete evidence-backed catalogue has **14
unique `(K,N)` shapes and exactly 532 GEMMs per target token**. The two hidden
calls are PLE value `[1,2560] @ [2560,2560]` and final HC-down
`[1,10240] @ [10240,320]`. The visible one-call
`[1,2560] @ [2560,10240]` is PLE key projection, not `lm_head`; logits are
outside A28's profiled `execute_context`.

This correction is fail-closed and preferable to forcing an incorrect
13-family accounting. It does not change A28's raw trace, protected speed, or
endpoint interpretation.

The complete 14-row extraction is now preserved as
`data/20260902-a28-bf16-dense-shape-catalog-top200.json`. It binds the four raw
trace hashes, summarizer hash and arguments, generated top-200 summary hash,
original recovered-summary hash, selection predicate, all shapes, and the
exact 532-call sum. The runtime catalog must match this artifact.

## Frozen scope

- actual revision `bcd9f01d...` BF16 checkpoint weights;
- all 14 A28 dense shape families, two early/late or rank-0/rank-3 sentinels
  each;
- seeds `2026090201`, `2026090202`, and `2026090203`;
- two independent worker processes per sentinel and seed: 168 total;
- active scheduler M values `1,2,4,8,16,32,48,64`;
- diagnostic-only M values `128,192,256`, which cannot describe this endpoint;
- 20 repeated calls plus reverse, cyclic, and seeded-random permutations;
- one selected B70, with one weight family resident at a time;
- weights only from the validated external `/dev/sda2` `fuseblk` checkpoint,
  never the internal root-NVMe copy;
- no vLLM server, container, full-checkpoint load, source change, reboot, or
  endpoint timing.

The authority is the same production XPU `torch.nn.functional.linear` applied
to each input row separately. A batch passes only if its full BF16 output is
byte-identical to those M1 rows, remains identical under every inverse row
permutation, and repeats to one hash. Inputs and weights must retain their
pre-run hashes. Checkpoint shape/dtype, TP4 sharding, model, source, Torch,
Python, `libsycl`, and `libtorch_xpu` identities fail closed.

Before any evidence directory is created or Torch/XPU is imported, the driver
requires the fixed-path validator to accept the current-boot root-NVMe
clearance receipt, verifies the exact external mount and recovered A28 summary
SHA, rejects tracked changes in either relevant source tree, and checks the
isolated interpreter, memory, swap, SMART, AER journal count, and exact four-XPU
topology. The same bounded admission runs between cells and at postflight.
Each cell is capped at 600 seconds and the plan at 21,600 seconds.

The driver resolves every selected tensor through the checkpoint index and
looks up its expected size and LFS SHA in the historical full verifier receipt
`6ae222...`, whose tree-metadata digest is `4a3793bd...`. It hashes each
selected external shard once and accepts it only if it matches that pre-existing
authority, then writes a no-clobber stat/SHA contract. Workers
recheck shard stats and record the selected source tensors, contract hash, and
reconstructed TP4-local weight hash. The singleton authority is independently
generated twice. Completion additionally requires matching replica input,
weight, singleton-authority, and full per-M result hashes across processes.

Worker subprocesses receive a fixed seven-variable execution environment plus
the explicit execution sentinel; extra GEMM-relevant `DNNL`, `MKL`, `SYCL`,
`ZE`, `LD`, `OMP`, `TORCH`, `VLLM`, `CCL`, or Q38 selectors are rejected. After
the GEMMs, `/proc/self/maps` must contain exactly the frozen `libsycl`,
`libtorch_xpu` integrated oneDNN provider, oneMKL BLAS/core, Level-Zero loader,
and Intel GPU provider binaries with their preregistered hashes and no separate
ambiguous `libdnnl` provider. Tracked changes in either provenance source tree
are rejected. Untracked source-tree files are deliberately excluded because
neither tree is imported by this component worker; the binaries it actually
loads are identified from live mappings and hashed instead.

Plan emission is CPU-only and authorizes no device work:

```bash
python3 experiments/qwen38-flash-next-fp8-b70/tools/census-q38-bf16-dense-invariance.py plan
```

The full plan requires the isolated vLLM Python, exact device selector, and an
explicit execution sentinel:

```bash
Q38_BF16_DENSE_CENSUS_EXECUTE=YES \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/census-q38-bf16-dense-invariance.py \
  run-plan
```

The evidence root is frozen and no-clobber. Each sentinel/seed/replica runs in
a distinct subprocess, and the final summary refuses missing or identity-
drifted cells.

## Frozen interpretation

A negative is useful classification evidence, not a runtime failure: preserve
it and expand only the affected high-cost family across every integer M from 1
through 64. A complete Phase-1 pass authorizes only a separately frozen
all-layer/all-rank Phase 2. Neither outcome by itself authorizes padding,
runtime dispatch changes, a full endpoint load, throughput credit, or a
quality/promotion claim.

Structured preregistration:
[`20260902-bf16-dense-invariance-phase1-prereg.json`](../data/20260902-bf16-dense-invariance-phase1-prereg.json).
