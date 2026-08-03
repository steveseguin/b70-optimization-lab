# Laguna INT4 affine one-cursor preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compile and static inspection of one
immutable source candidate. It does not authorize executing the output, loading
an XPU component, importing or probing the XPU runtime, model/service work,
reset, recovery, or privilege. The corrected PCIe/NVMe quarantine remains
unchanged.

## Causal successor and bounded claim

The preserved two-cursor source `dd597391f22f` passed the historical 378 static
topology ceiling at 377 total / 325 ALU instructions, exact sends and sync
metric 9, while removing both recurring dynamic weight-address `mul ... 1152`
operations. It remained unpromoted because it regressed the clean scale-clone
base `86c1c8bdf75b` at 371 total / 319 ALU.

Its exact opcode delta from the scale-clone base was +7 `mov`, +1 `add`, and -2
`mul`. Manual attribution found five new moves in the six-way unrolled weight
prefetch prologue: the mutable prefetch cursor made IGC form each constant
record address in a temporary and then move it into the payload. A one-time add
also formed the record-six cursor before the main loop, and the separate future
cursor required its own payload move and recurring increment.

Candidate source `2dc2b2a867ff`, guarded by follow-up test commit
`683265470c5c`, tests whether eliminating that separate mutable cursor lets IGC:

1. fold the six prologue payload bases directly from the immutable record-zero
   base plus compile-time record offsets; and
2. derive the guarded future base from the already-advanced copy cursor plus
   five record strides.

For the frozen K256 / group-size32 / tile-K32 / prefetch-distance6 probe, the
prologue addresses records 0..5. After copying record `k`, the sole mutable
cursor names record `k+1`; adding `(6 - 1) * 1152` names future record `k+6`, so
the guarded path issues records six and seven and no record eight.

No pre-AOT claim is made that instruction count, ALU count, address overhead,
or performance improves. The rank-2 payloads, 1152-byte format, scale tensor
and clone, values, scalar scale loads, arithmetic and K order, prefetch distance,
DPAS, output, selector-false isolation, and MXFP4 fallback are unchanged.

Candidate identity:

- tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-one-cursor-20260803`;
- branch: `experiment/laguna-int4-affine-one-cursor-20260803`;
- base / bounded two-cursor commit:
  `dd597391f22f6a5f15ccbc0c6b115005970b4575`;
- source commit:
  `2dc2b2a867ffd7d07428e1d65e584c4d3b64afa3`;
- candidate head / final source guards:
  `683265470c5cdb30115c1027e6f0ad6780819d7e`;
- frozen dependency commit:
  `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- source patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-share-INT4-tile-record-weight-cursor.patch`;
- source patch SHA-256:
  `c1e4af603ab5ff8dcfbc46c5220d74fb97e990cd4447ae371e1c33c1b41014cd`;
- guard patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-strengthen-one-cursor-static-guards.patch`;
- guard patch SHA-256:
  `a60ccbce4471d2aea1d3942f8670094ee3b41619cfcbd9094486b9c4f034bc13`.

Pre-AOT evidence is limited to 5/5 final source guards, Ruff,
`git diff --check`, a successful full matched-probe oneAPI 2025.3
`-fsycl -fsyntax-only` instantiation of the source commit, and independent
source/test/honesty review. It is not ISA, output-correctness, performance, or
memory evidence.

The existing prologue is bounded by `prefetch_dist`, not `k_tile_count`; a
distance larger than the tile count can prefetch beyond both A and the record
array. That behavior predates this candidate and is unchanged. This screen is
strictly K256/G8/distance6, where six prologue issues are in bounds; it makes no
claim about other overrides or routes.

## Frozen compile-only action

Compile the existing two-kernel K256 probe once into this new output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-one-cursor-683265470c5c-20260803T020000
```

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-one-cursor-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-one-cursor-683265470c5c-20260803T020000
```

Never invoke the emitted executable.

## Frozen automated gate

Exactly one selector-false `ILb0EE` and selector-true `ILb1EE` assembly must
exist. Selector-false must reproduce the exact archived control: 370 total, 320
ALU, sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, 2 DPAS,
33 analyzer plain multiplies, GRF128, no executable spill/scratch, archived
memory/send/sync histogram, and normalized body identity except options/hash
header and terminal hash sentinels.

Selector-true is a no-regression pass only if every condition holds:

1. total instructions are at most **371** and ALU instructions at most **319**,
   matching or improving the clean scale-clone base;
2. it retains 2 DPAS, 33 analyzer plain multiplies, and unchanged normalized
   arithmetic body/order;
3. sync metric is exactly 9 with zero `sync.allrd`, nine `sync.nop`, one
   `sync.bar`, and complete archived memory/send/sync opcode identity;
4. it uses GRF128 with no executable scratch/spill;
5. total executable root opcodes satisfy `mov <= 145`, `add <= 59`, `mul <= 35`,
   `macl == 1`, `mad == 1`, and `shl == 11`, with no `add3` or equivalent
   replacement arithmetic; and
6. there is no recurring executable multiply by decimal 1152 or hexadecimal
   0x480 in the traversal and no equivalent multiply-add, division, modulo, or
   shift/add record-stride reconstruction.

The opcode limits express at most +2 `mov`, +0 `add`, and -2 `mul` relative to
the clean 371-instruction scale-clone assembly. Constant prologue address adds
are allowed. The analyzer's 33 plain-multiply anchor does not count the prior
predicated address multiplies, so conditions 5 and 6 require supplemental
numeric parsing and manual attribution.

## Frozen manual gate and classification

Manual inspection must prove all of the following:

- the six prologue weight bases normalize to record offsets
  `{0, 1152, 2304, 3456, 4608, 5760}` from one immutable base;
- their payload base formation contains none of `dd59739`'s five temporary
  address-to-payload moves;
- one and only one mutable record cursor/phi exists, copy issues records 0..7,
  and it advances once after each copy;
- future weight prefetch issues only records six and seven by adding 5760 bytes
  to the already-advanced copy cursor, with no separate prefetch cursor,
  increment, setup, or phi;
- every weight issue lowers as cursor/constant-derived base retarget, rank-2
  X/Y update, unchanged send, with no second base write before the send;
- the cloned-scale issue block remains at most four instructions; and
- the future combined weight-prefetch block is strictly shorter than the
  two-cursor build's ten instructions and no longer than nine.

Results are classified without changing the source:

- at most 371 total and 319 ALU plus all other gates: offline
  no-count-regression/static address-lowering pass;
- 372..376: partial count cleanup from 377, but still worse than the clean base
  and not promoted;
- 377..378: fails the one-cursor cleanup objective despite the historical
  ceiling; and
- above 378 or any topology/address/sync failure: hard static loss.

Even the strongest pass is offline lowering evidence only for K256/G8/d6. It
does not authorize a DSO, device component, model integration, timing,
exactness claim, memory-feasibility claim, submission, or record claim. The
15.1875-GiB/rank allocation, 13.5-GiB/rank net-growth hard stop, device
quarantine, and protected 125.461973 conventional tok/s record remain
unchanged.
