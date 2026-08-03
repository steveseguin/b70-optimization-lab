# Laguna INT4 affine canonical-cursor preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compile and static equivalence check
of one immutable source candidate. It does not authorize executing the output,
loading an XPU component, importing or probing the XPU runtime, model/service
work, reset, recovery, or privilege. The corrected PCIe/NVMe quarantine remains
unchanged.

## Canonical-source equivalence question

Candidate `683265470c5c` produced a strong 370-total / 318-ALU assembly with
exact topology and no dynamic weight-address `mul ... 1152`, but missed its
frozen literal manual gate. Source expressed future address formation as
advanced cursor plus 5760; IGC reassociated it into current cursor plus 6912
and moved the +1152 cursor induction to the loop latch. The addresses were
semantically exact, but the result was correctly not retroactively awarded the
literal-form pass.

Candidate `58092a5a4361` is a new source-ordering commit that directly expresses
the compiler's canonical form:

1. copy uses the current-record cursor;
2. guarded future prefetch uses that same cursor plus
   `prefetch_dist * 1152`;
3. the cursor advances once outside and after the complete future conditional,
   on every natural loop path; and
4. the next iteration therefore sees the next record.

For frozen K256/G8/distance6 this is current record `k` +6912 = record `k+6`,
then one +1152 induction. The prologue remains records 0..5; copy remains
records 0..7; guarded future remains records six and seven.

This is not a second optimization/mechanism claim and not a rerun or
reinterpretation of `6832654`. The only prospective question is whether source
and literal gate can be aligned while reproducing the already archived
executable body exactly after permitted hash normalization.

Candidate identity:

- tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-canonical-cursor-20260803`;
- branch: `experiment/laguna-int4-affine-canonical-cursor-20260803`;
- base / literal-shape-miss head:
  `683265470c5cdb30115c1027e6f0ad6780819d7e`;
- candidate commit:
  `58092a5a436170921208da96b8fd713a9d954071`;
- frozen dependency commit:
  `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-canonicalize-INT4-tile-record-cursor-order.patch`;
- patch SHA-256:
  `6b16241d7af365934b58b50261478f29b4d98fff68a77cc5419bb9ac142e56e9`;
- archived semantic predecessor assembly:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-one-cursor-683265470c5c-20260803T020000/OCL_asm03a06e1f2fe9faed_simd16_entry_0002.asm`;
- archived predecessor raw assembly SHA-256:
  `946f64d14566ae84a12b7eb94b5b4342700ee4faae1f5284168ab3cf81fd9d69`.

Pre-AOT evidence is limited to 5/5 strengthened source guards, Ruff,
`git diff --check`, a successful full matched-probe oneAPI 2025.3
`-fsycl -fsyntax-only` instantiation, and independent source/test/honesty
review. It is not ISA, output-correctness, performance, or memory evidence.

The inherited prologue is bounded by `prefetch_dist`, not `k_tile_count`. This
screen remains strictly K256/G8/distance6, where all six prologue issues are in
bounds; it makes no claim about other overrides or routes.

## Frozen compile-only action

Compile the existing two-kernel K256 probe once into this new output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-canonical-cursor-58092a5a4361-20260803T021500
```

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-canonical-cursor-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-canonical-cursor-58092a5a4361-20260803T021500
```

Never invoke the emitted executable.

## Frozen exact-equivalence gate

Exactly one selector-false `ILb0EE` and selector-true `ILb1EE` assembly must
exist.

Selector-false must reproduce the archived control exactly: 370 total / 320
ALU, sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, 2 DPAS,
33 analyzer plain multiplies, GRF128, no executable spill/scratch, archived
memory/send/sync histogram, and normalized body identity except options/hash
header and terminal hash sentinels.

Selector-true passes only if it exactly reproduces the archived `6832654`
executable body after excluding those same options/hash-header and terminal
hash-sentinel differences. Exact body identity is the primary gate; no better
or equal count can waive a body difference.

The exact reproduction anchors are:

- 370 total / 318 ALU;
- root opcodes `mov=144`, `add=59`, `mul=35`, `macl=1`, `mad=1`, `shl=11`,
  `add3=0`;
- 2 DPAS and 33 analyzer plain multiplies with unchanged normalized arithmetic
  order/body;
- exact archived memory/send/sync histogram;
- sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`;
- GRF128 and no executable spill/scratch;
- cloned-scale issue block exactly four instructions; and
- combined future block exactly nine instructions.

Manual IR/ISA inspection must additionally prove:

1. one current-record cursor/phi feeds both the main weight copy and future
   weight-prefetch base;
2. the future path contains exactly one literal add of decimal 6912 or
   hexadecimal 0x1b00 from that current cursor, before rank-2 X/Y updates and
   the unchanged d8 prefetch send;
3. exactly one unconditional cursor add of decimal 1152 or hexadecimal 0x480
   occurs at the future-branch join/latch before the next backedge;
4. no future-path +5760 form, second record cursor/phi, setup, or increment
   exists;
5. prologue bases remain direct immutable-base offsets
   `{0, 1152, 2304, 3456, 4608, 5760}`;
6. copy issues records 0..7, guarded future issues records six and seven only,
   and no record eight base write/send occurs; and
7. no dynamic record-stride multiply or equivalent reconstruction exists.

Any selector-true normalized body difference fails this canonical-reproduction
gate, even if counts improve or semantic addresses remain valid. Such a result
must be recorded descriptively and studied only under a new prospective gate.

An exact pass establishes only **canonical-source static equivalence** for
K256/G8/distance6. It does not retroactively pass `6832654`, re-credit the
already observed count reduction, establish output exactness or speed, or
authorize a DSO, device component, model integration, timing, memory-feasibility
claim, submission, or record claim. The 15.1875-GiB/rank allocation,
13.5-GiB/rank net-growth hard stop, device quarantine, and protected
125.461973 conventional tok/s record remain unchanged.
