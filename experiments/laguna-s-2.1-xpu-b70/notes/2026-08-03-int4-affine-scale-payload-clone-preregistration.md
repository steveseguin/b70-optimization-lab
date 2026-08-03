# Laguna INT4 affine scale-payload clone preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This packet authorizes one offline BMG AOT compile and **scale-payload
feasibility sub-screen** of one immutable source candidate. It does not
authorize executing the output, XPU
runtime import/probing, model/service work, reset, or privilege. The corrected
PCIe/NVMe error quarantine remains unchanged.

## Distinct successor

The closed per-issue-scale-prefetch hybrid `698113420380` recovered exact
synchronization and memory/send topology but compiled at 386 instructions,
eight above the frozen ceiling. Its repeated full scale descriptor
construction accounted for the remaining overhead.

The frozen CUTLASS dependency declares an otherwise-unused
`__builtin_IB_subgroup_copyBlock2DAddressPayload` intrinsic. Candidate
`86c1c8bdf75b` restores one fully initialized affine rank-2 scale-prefetch
master inside the true-only state, but never issues that master. Each source
prefetch site shallow-copies the typed TiledCopy and then deep-clones its
hardware payload with the intrinsic before updating its group coordinate and
issuing. This is intended to preserve invariant base/width/height/1152-byte
pitch fields while giving every issue a non-aliasing payload.

The affine weight path, scalar scale loads, record format, values, arithmetic,
K order, prefetch distance, DPAS, output, compile-time false isolation, and
MXFP4 fallback are unchanged. A plain C++ copy would alias the mutable payload;
the deep-copy intrinsic is the entire new mechanism.

Candidate identity:

- tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-scale-clone-20260803`;
- branch: `experiment/laguna-int4-affine-scale-clone-20260803`;
- base / closed hybrid commit:
  `698113420380b3e343a04ab93321c7adf0b1e94e`;
- candidate commit:
  `86c1c8bdf75bbd84803f4d256b925b3f509e5ea4`;
- dependency commit:
  `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-clone-affine-scale-prefetch-payloads.patch`.

The candidate relies on the dependency's internal
`cute::detail::as_block_2d_traits` helper and mutable public `payload` field.
The copy intrinsic is declared but unexercised in this dependency revision;
failure to lower, an unexpectedly large expansion, payload coalescing, or
restored waits are all possible and count as results, not reasons to retry.

Pre-AOT evidence is limited to 5/5 source guards, Ruff, `git diff --check`, and
a successful full matched-probe oneAPI 2025.3 `-fsycl -fsyntax-only`
instantiation. It is not ISA, correctness, performance, or memory evidence.

## Frozen compile-only action

Compile the existing two-kernel K256 probe once into this new output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-scale-clone-86c1c8bdf75b-20260803T020000
```

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-scale-clone-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-scale-clone-86c1c8bdf75b-20260803T020000
```

Never invoke the emitted executable.

## Frozen gate

Exactly one selector-false `ILb0EE` and selector-true `ILb1EE` assembly must
exist. Run the unchanged analyzer and preserve normalized/manual comparison.

Selector-false must reproduce the exact archived control: 370 total, 320 ALU,
sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, 2 DPAS, 33
plain multiplies, GRF128, no executable spill/scratch, archived opcode
histogram, and normalized body equality except options/hash header and terminal
hash sentinels.

Selector-true passes only if every condition holds:

1. total instructions at most 378;
2. 2 DPAS, 33 plain multiplies, and unchanged normalized arithmetic body/order;
3. sync metric exactly 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`,
   and complete archived memory/send/sync opcode identity;
4. GRF128 with no executable scratch/spill;
5. steady future-prefetch block at most eight instructions; and
6. no recurring **scale-prefetch** multiply-by-1152 or full scale-descriptor
   reconstruction in the K/prologue traversal.

This sub-screen does not waive the broader tile-record gate. The affine rank-3
weight copy and weight prefetch are expected to retain two group-stride base
computations. Even if the scale clone passes every condition above, the result
only authorizes a separately committed, separately preregistered source-only
attempt to replace those weight multipliers with pointer induction or another
exact address formulation. It is not a full static pass for timing.

Any compiler failure or selector-false miss closes this source result. Any
selector-true miss closes the scale-clone mechanism as a static loss. A low
count cannot waive waits, and a clean wait topology cannot waive the ceiling.
Do not retry this commit, change the gate, or perform timing. A sub-screen pass
would not authorize device work.

The 13.5-GiB/rank memory hard stop, device quarantine, and protected
125.461973 conventional tok/s record remain unchanged.
