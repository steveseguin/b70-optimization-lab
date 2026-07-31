# Laguna INT4 dequant-MAD in-place GRF preregistration

Date: 2026-07-31 America/Toronto

## Premise

The verified `VLLM_XPU_LAGUNA_SCALE_VEC=1` change won by 2.09% at the matched
median after removing operand-marshalling moves from the dominant width-12
INT4 grouped-GEMM mainloop. It changed no arithmetic: it named the full GRF
already holding a channel pair and let the existing multiplies read it
directly.

The exact dequant-MAD path is the closest remaining analogue. It replaces the
incumbent bias-add plus scale-multiply with the mathematically and bitwise
equivalent operation

```text
(x - 136) * scale == x * scale + (-136 * scale)
```

and is already exhaustively verified across all INT4 values and all 65,536
BF16 scale bit patterns, subject to its existing overflow gate. Its first
implementation cut float-pipe work from 65 to 36 instructions per k-tile but
grew the integer pipe from 50 to 65 and measured about 1% slower end to end.

Source inspection shows the pair form receives the same full GRF twice: once
as a write-only destination and once as a separate read-only source, even
though both C++ references alias the same channel-pair object. The scale-vector
win suggests that forcing the MAD to read and write that one full-GRF operand
in place may remove the extra bindings without changing either MAD, its
operands, its destination type, or its order.

## Candidate

Change only `apply_scale_pair_mad` in
`csrc/xpu/grouped_gemm/xe_2/gemm_xe2.hpp`:

- remove the duplicate `s` function/assembly operand;
- name the 32-element BF16 pair through one `+rw` full-GRF operand; and
- use that same declared GRF as both MAD source and destination.

The selector remains `VLLM_XPU_LAGUNA_DEQUANT_MAD=1`, default off. The
incumbent `DEQUANT_MAD=0` binary path must remain unchanged. No model, weight,
KV dtype, speculative policy, reduction, output, or measurement rule changes.

## Stage gates

1. Work from kernel commit
   `46a88e09d96fe06871c87a23de534fb47f1e039b` on a dedicated experiment
   branch. Do not modify the installed incumbent binary.
2. Compile the grouped-GEMM library with the same oneAPI toolchain and inspect
   the generated width-12 decode policy ISA.
3. Stop before any GPU endpoint if any of these hold:
   - DPAS count differs from the incumbent or first MAD implementation;
   - spill/fill becomes nonzero;
   - float arithmetic differs from the two existing MAD instructions;
   - the mainloop does not remove at least eight integer/data-movement
     instructions versus the first MAD path; or
   - total dynamic mainloop instruction count is not lower than the first MAD
     path.
4. If ISA passes, run the existing component exactness gate against both the
   incumbent `DEQUANT_MAD=0` and first `DEQUANT_MAD=1` results. Require bitwise
   equality over every output tensor and the existing adversarial scale
   populations. Stop on the first mismatch or device/runtime error.
5. Only then mint a candidate runtime lock and run one cold scored leg on the
   verified 121.037 BF16-KV vLLM configuration, with target 146/145 and draft
   14/13 topology unchanged. No diagnostic run may be quoted as throughput.
6. A first exact scored improvement inside the known noise band requires an
   interleaved confirmation before promotion. A loss is retained and closed.

No reboot, reset, FLR, driver reload/unbind, shared-memory deletion, metric
window change, quality relaxation, teacher regeneration, or best-of-run
selection is authorized.

## Expected value

This is not projected to reach 130 tok/s alone. It is worth attempting because
it attacks the measured dominant graph-segment kernel using the only pattern
that has produced a repeatable exact kernel win here. The compile-time ISA gate
keeps a failed codegen idea from consuming a scored GPU leg.
