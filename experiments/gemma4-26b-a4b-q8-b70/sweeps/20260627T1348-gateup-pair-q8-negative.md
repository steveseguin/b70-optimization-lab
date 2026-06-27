# 2026-06-27T13:48Z Gate/Up Pair Q8 Kernel Negative

## Question

Can the Q8_0 `ffn_moe_gate_up` verifier path get faster by computing each
matching gate/up row pair in one workgroup, sharing the quantized activation
row (`y`) load and writing the existing output layout unchanged?

This was suggested by the remaining target/verifier MoE bottleneck after the
current `104.30919255569083 tok/s` Gemma 4 26B A4B Q8 one-B70 record. It is
distinct from the earlier graph-level `GGML_MOE_Q8_0_GATEUP_GEGLU` lane.

## Patch

Source patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/gateup-pair-q8-negative-20260627.patch`

The patch added a default-off flag:

```text
LLAMA_SYCL_MUL_MAT_ID_GATE_UP_PAIR_Q8_0=1
```

It added a Q8_0-only `MUL_MAT_ID` paired gate/up kernel and routed only
`ffn_moe_gate_up` nodes with non-reordered Q8_0 weights and even `nrows`.

## Result

Candidate:

- run: `data/gemma4-q8-gpu1-gateup-pairq8-ub768-screen-20260627T1348Z/`
- GPU/port: GPU1 / `18311`
- flag: `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_PAIR_Q8_0=1`
- canary: `256/256`, pass
- fresh row0 after-TTFT: `84.75499805492217 tok/s`
- support mean after-TTFT: `84.70392311769213 tok/s`

Control, same rebuilt binary/source stack:

- run: `data/gemma4-q8-gpu2-gateup-pairq8-control-ub768-screen-20260627T1348Z/`
- GPU/port: GPU2 / `18312`
- flag: unset
- canary: `256/256`, pass
- fresh row0 after-TTFT: `104.28417032791086 tok/s`
- support mean after-TTFT: `104.02314890893228 tok/s`

## Decision

Reject. The candidate is quality-clean but much slower:

```text
84.755 vs 104.284 tok/s row0 fresh = -18.65%
```

Do not promote, do not submit to LocalMaxxing, and do not leave the flag live
in the working tree. The likely reason is higher register pressure and reduced
occupancy from accumulating two rows in the same workgroup; the saved activation
row load is not the bottleneck at this shape.

Future work should not retry this exact paired gate/up row body. A different
MoE gate/up specialization would need evidence that it reduces register
pressure or fuses useful epilogue work rather than just pairing rows.
