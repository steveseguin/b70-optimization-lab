# Laguna INT4 affine tile-record static-screen preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compilation and static inspection.
It does **not** authorize executing the emitted binary, importing or probing an
XPU runtime, loading a model, touching the service, resetting a device, or
performing any privileged recovery action. Corrected PCIe RxErrs on the
root-filesystem NVMe during the consumed swap24 smoke keep all device work
quarantined until separate authorization.

## Why this is distinct from the closed attempt

The 2026-07-31 INT4 tile-record experiment tested this immutable record format:

```text
[1024 untouched packed-INT4 bytes][128 untouched BF16 scale bytes]
```

for every N64 x K32 tile. Its matched K256 BMG probe preserved 2 DPAS and 33
unpredicated multiplies but grew from 370 to 468 instructions because the
source rebuilt dynamic tensors and block-copy payloads inside the K traversal.
That implementation was correctly closed before device timing. Its note named
the only credible successor: one affine/hierarchical view constructed outside
the K loop.

This candidate implements that successor, not a new physical-layout claim. It
constructs one rank-3 `[N64,K32,K-group]` packed-weight view and one rank-2
`[N64,K-group]` scale view before the prologue. The K traversal selects only
the affine group coordinate. The INT4 route is compile-time isolated so the
existing MXFP4 TileMajor construction remains unchanged.

Historical identity correction: the old note abbreviates the source as
`7af3f6204f`, which is not a valid object. The actual preserved commit and this
candidate's base are
`7af3f622d9bf0850661d69045fab18a188ca83f4`.

Candidate identity:

- source tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-tile-record-20260803`;
- branch: `experiment/laguna-int4-affine-tile-record-20260803`;
- commit: `a0c7ae628ff1249c3fb105220b4dd664b960ad95`;
- changed source:
  `csrc/xpu/grouped_gemm/xe_2/gemm_xe2.hpp`;
- source guard test:
  `tests/test_laguna_int4_affine_tile_record_static.py`;
- patch snapshot:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-hoist-INT4-tile-records-into-affine-views.patch`.

Pre-AOT host evidence is limited to 5/5 static tests, Ruff, `git diff --check`,
and a clean `icpx 2025.3 -fsycl -fsyntax-only` header compilation. It is not
an ISA, correctness, performance, or memory-feasibility result.

## Frozen compile-only action

Run the existing matched two-kernel K256 probe exactly once into this new,
nonexistent output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-tile-record-a0c7ae628ff1-20260803T010500
```

The frozen command is:

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-tile-record-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-tile-record-a0c7ae628ff1-20260803T010500
```

Dependency source is commit
`cd763790ad2f74d7294435ecf77682bac0062c3a`. The probe must only be compiled;
its emitted executable must never be run because `main()` allocates XPU memory
and launches both kernels.

## Frozen static gate

The new analyzer
`tools/analyze_laguna_int4_tile_record_aot.py` must first find exactly one
selector-false/control assembly (`ILb0EE`) and one
selector-true/candidate assembly (`ILb1EE`). Nonmatching IGC dumps are ignored.

The fresh selector-false kernel must reproduce the archived control after
allowing only hash-seed/header and terminal hash-move differences:

- 370 total instructions;
- 320 ALU instructions;
- 9 synchronization instructions;
- 2 DPAS and 33 plain, unpredicated multiplies;
- GRF128;
- no executable scratch or spill operations.

Archived control assembly SHA-256 is
`d6f5cac78eb4e16758cb73bafbf741bf7af2a99659f7ebc60b5fcefef9271fec`.
If the fresh control misses the metrics above, this comparison is invalid; do
not compare only against the archived candidate. Rebuild historical control
and treatment from fresh immutable trees in a separately recorded action.

The affine candidate passes this screen only if all of the following hold:

1. total instructions are at most **378**, allowing at most eight one-time
   setup instructions above the 370-instruction control;
2. DPAS remains 2, unpredicated multiply remains 33, and arithmetic order/body
   is unchanged under normalized assembly inspection;
3. synchronization count remains 9 and the memory/send opcode histogram is
   identical to control;
4. GRF remains 128 with no executable spill or scratch operation;
5. the steady future-prefetch block is no longer than the control's eight
   instructions; and
6. normalized inspection finds no recurring multiply-by-1152 or copy-descriptor
   materialization in the K/prologue traversal.

The analyzer enforces cardinality, the numeric ceiling, arithmetic anchors,
sync count, memory/send opcode identity, GRF, and executable spill/scratch
absence. Items 2, 5, and 6 also require a preserved normalized/manual diff.

Any result above 378 instructions, any GRF/spill regression, or any changed
arithmetic, synchronization, or memory/send topology closes this source
candidate as a static loss. Do not relax the threshold after seeing the dump,
and do not time a failed candidate. A pass establishes only that the source
overhead problem was removed; it does not authorize device work.

## Memory hard stop

Full W13+W2 records across 48 layers and 64 local experts require
`16,307,453,952` bytes per rank (`15.1875 GiB`). Even if the records replace the
current `1,811,939,328`-byte transposed-scale clone while the original weights
remain for prefill, persistent growth is still `14,495,514,624` bytes
(`13.5 GiB`) per rank. Recent initialization pressure makes duplication a hard
no-go.

Therefore no model integration follows directly from an AOT pass. A future
packet must prove a replacement design in which every required prefill,
decode, and other-M consumer can use the records and the original weights plus
transposed-scale clone are absent. That work remains behind both a memory gate
and the separate device-safety authorization boundary.

The protected 125.461973 conventional tok/s record remains unchanged.
