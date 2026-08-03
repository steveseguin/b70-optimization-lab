# Laguna INT4 affine-weight / per-issue-scale-prefetch preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compile and static inspection of a
third immutable source candidate. It does not authorize executing the output,
an XPU runtime import/probe, model/service work, device reset, or privilege.
The PCIe/NVMe corrected-error quarantine remains unchanged.

## Exact successor delta

The compile-time state candidate `1ef527526e8c` recovered the selector-false
control exactly at 370/320/sync-9, but selector-true remained 369/317/sync-10
with four `sync.allrd`. Source/ISA review localized those waits to repeated
coordinate updates on one hoisted mutable scale-prefetch payload; the affine
weight payload was not the direct source.

Candidate `698113420380` makes only the preregistered hybrid change:

- retain compile-time isolation;
- retain the affine rank-3 packed-weight view, copy, and prefetch payload;
- retain the affine rank-2 scale tensor for scalar scale loads;
- remove the hoisted scale-prefetch copy/partition/payload state; and
- use the existing TileMajor per-issue scale-prefetch construction at both
  prefetch sites.

Record format, packed values, scale values, arithmetic, K order, prefetch
distance, DPAS, outputs, and MXFP4 fallback are unchanged.

Candidate identity:

- tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-hybrid-prefetch-20260803`;
- branch: `experiment/laguna-int4-affine-hybrid-prefetch-20260803`;
- base / closed compile-time-state candidate:
  `1ef527526e8ca18e7c04dc9bb8b23020e6f8dec2`;
- commit: `698113420380b3e343a04ab93321c7adf0b1e94e`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-use-per-issue-tile-record-scale-prefetch.patch`.

Pre-AOT evidence is limited to 5/5 static guards, Ruff, `git diff --check`, and
a successful full matched-probe oneAPI 2025.3 `-fsycl -fsyntax-only`
instantiation. It is not ISA, correctness, performance, or memory evidence.

## Frozen compile-only action

Compile the same two-kernel K256 probe once into the new output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-hybrid-698113420380-20260803T014000
```

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-hybrid-prefetch-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-hybrid-698113420380-20260803T014000
```

Dependency commit remains
`cd763790ad2f74d7294435ecf77682bac0062c3a`. Never invoke the emitted
executable.

## Frozen gate

Require exactly one selector-false `ILb0EE` and selector-true `ILb1EE`
assembly. Run the unchanged AOT analyzer and preserve a normalized/manual ISA
comparison.

Selector-false is valid only at the exact archived identity: 370 total, 320
ALU, sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, 2 DPAS,
33 plain multiplies, GRF128, no executable spill/scratch, archived opcode
histogram, and normalized body equality apart from options/hash header and
terminal hash sentinels.

Selector-true passes only with every condition below:

1. total instructions at most 378;
2. 2 DPAS, 33 plain multiplies, and unchanged normalized arithmetic body/order;
3. sync metric exactly 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`,
   and the complete archived memory/send/sync opcode histogram;
4. GRF128 with no executable scratch/spill;
5. steady future-prefetch block at most eight instructions; and
6. no recurring multiply-by-1152 or copy-descriptor reconstruction in the
   K/prologue traversal.

Any selector-false miss invalidates comparison and closes this isolation base.
Any selector-true miss closes the hybrid as a static loss. A low instruction
count cannot waive synchronization. Do not retry this commit, change a gate,
or perform timing after failure. A full static pass still would not authorize
device work.

The 13.5-GiB/rank net-growth memory hard stop, device quarantine, and protected
125.461973 conventional tok/s record remain unchanged.
