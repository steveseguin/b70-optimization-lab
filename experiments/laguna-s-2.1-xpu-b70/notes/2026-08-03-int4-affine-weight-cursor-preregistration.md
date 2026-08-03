# Laguna INT4 affine weight-cursor preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compile and static inspection of one
immutable source candidate. It does not authorize executing the output, loading
an XPU component, importing or probing the XPU runtime, model/service work,
reset, recovery, or privilege. The corrected PCIe/NVMe error quarantine remains
unchanged.

## Distinct successor and bounded claim

The clean scale-payload-clone source `86c1c8bdf75b` compiled at 371 total / 319
ALU instructions with sync metric 9, zero `sync.allrd`, exact archived
memory/send topology, GRF128, and no executable spill/scratch. It left two
recurring dynamic weight-address `group * 1152` calculations: one in the weight
copy and one in the future weight prefetch.

Candidate `dd597391f22f` tests whether replacing those two rank-3 weight
coordinates with independent induced byte cursors removes their recurring
multiplies without changing descriptor geometry, issue order, sends, waits, or
the proven scale clone. It makes the weight surface rank-2 N64/K32 with stride
(32,1), initializes copy and prefetch cursors at record zero, retargets the
corresponding persistent payload immediately before each issue, and advances
that cursor by the 1152-byte record size immediately afterward.

This mechanism is source-plausible because the frozen CUTLASS block-2D x/y
modes consume both rank-2 tensor strides. `nontrivial_tiled_strides` is therefore
false: the issue-time coordinate update sets only X/Y and cannot restore the
master payload's original base after the explicit cursor retarget.

No pre-AOT claim is made that instruction count, ALU count, address overhead,
or performance improves. The record format, values, scale tensor and clone,
scalar scale loads, arithmetic and K order, prefetch distance, DPAS, output,
compile-time false isolation, and MXFP4 fallback are unchanged.

Candidate identity:

- tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-weight-cursor-20260803`;
- branch: `experiment/laguna-int4-affine-weight-cursor-20260803`;
- base / clean scale-clone commit:
  `86c1c8bdf75bbd84803f4d256b925b3f509e5ea4`;
- candidate commit:
  `dd597391f22f6a5f15ccbc0c6b115005970b4575`;
- frozen dependency commit:
  `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-induce-INT4-tile-record-weight-addresses.patch`;
- patch SHA-256:
  `7790586f32ce4a7effa101b0b20a9c78acd4bd6275285123a380b902ec0e1bc1`.

Pre-AOT evidence is limited to 5/5 strengthened source guards, Ruff,
`git diff --check`, two successful full matched-probe oneAPI 2025.3
`-fsycl -fsyntax-only` instantiations around the final invariant change, and
independent source/test/honesty review. The source proof covers K256 / eight
records / prefetch distance six: the prefetch cursor issues records 0..5 in the
prologue and 6..7 in the guarded future path, while the copy cursor issues
records 0..7. It is not ISA, output-correctness, performance, or memory evidence.

## Frozen compile-only action

Compile the existing two-kernel K256 probe once into this new output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-weight-cursor-dd597391f22f-20260803T014500
```

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-weight-cursor-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-weight-cursor-dd597391f22f-20260803T014500
```

Never invoke the emitted executable.

## Frozen automated gate

Exactly one selector-false `ILb0EE` and selector-true `ILb1EE` assembly must
exist. Run the unchanged analyzer and preserve normalized/manual comparison.

Selector-false must reproduce the exact archived control: 370 total, 320 ALU,
sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, 2 DPAS, 33
plain multiplies, GRF128, no executable spill/scratch, archived opcode
histogram, and normalized body equality except options/hash header and terminal
hash sentinels.

Selector-true passes the established full offline static ceiling only if every
condition holds:

1. total instructions are at most 378; record separately whether it also has
   no count regression from the 371-total / 319-ALU scale-clone base;
2. it retains 2 DPAS, 33 analyzer plain multiplies, and unchanged normalized
   arithmetic body/order;
3. sync metric is exactly 9 with zero `sync.allrd`, nine `sync.nop`, one
   `sync.bar`, and complete archived memory/send/sync opcode identity;
4. it uses GRF128 with no executable scratch/spill;
5. the recurring copy and future-weight-prefetch paths contain zero executable
   dynamic multiply by decimal 1152 or hexadecimal 0x480, and no equivalent
   division, modulo, multiply-add, shift/add reconstruction, or full descriptor
   rebuild; and
6. the scale-clone future-prefetch block remains at most four instructions and
   the future weight-prefetch block remains at most the scale-clone base's ten
   instructions, with the same sends and roles.

The analyzer's 33 plain-multiply anchor does not count the prior predicated
weight-address multiplies, so condition 5 requires a separate numeric opcode
search plus manual block attribution. A one-time workgroup record-base
calculation may still contain `* 1152`; unrolled constant pointer adds such as
`+1152` and `+2304` are also allowed. Neither may be misclassified as one of
the two recurring traversal multiplies targeted here.

## Frozen manual gate and interpretation

For every weight copy/prefetch issue, inspect the lowered sequence and require:

1. a cursor-derived payload-base write;
2. the rank-2 coordinate-zero X/Y updates;
3. the unchanged weight send;
4. no second base write between the cursor retarget and send; and
5. cursor advancement by induction/add only after that issue.

The K256 probe must address copy records 0..7 exactly once and prefetch records
0..5 then 6..7 exactly once. No payload, send, record, or scale-clone issue may
be missing or duplicated.

A result at 371/319 or better that meets every gate is a no-count-regression
offline cursor-lowering/static-topology pass. A 372..378 result meeting every
other gate validates the bounded cursor mechanism under the established full
static ceiling but is explicitly an instruction-count regression from the
clean scale-clone base and must remain in source cleanup; it is not a promoted
optimization. Any result above 378, any recurring target multiply, any wait,
send/descriptor change, overwritten base, spill, or false-control miss closes
the candidate as a static loss. Do not retry or change the frozen source.

Even the strongest pass is only offline address-lowering evidence. It does not
authorize a DSO, device component, model integration, timing, exactness claim,
memory-feasibility claim, submission, or record claim. The 15.1875-GiB/rank
allocation, 13.5-GiB/rank net-growth hard stop, device quarantine, and protected
125.461973 conventional tok/s record remain unchanged.
