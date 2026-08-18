# Qwen3.8 27B Q8 TP2 attention-triple workgroup sweep

Date: 2026-08-17

Status: closed; performance-neutral, not promoted.

## Hypothesis

The accepted recurrent GDN quad benefited from grouping 24 independent SG16
rows in each workgroup instead of the generic eight. The fused full-attention
Q/V/K projection is a separate Q8 MMVQ family, appears 32 times per decoded
token across TP2, and has not received a shape-scoped workgroup sweep. Its
three projections share one reordered activation, so a different workgroup
population may improve scheduling or cache reuse without changing arithmetic.

## Contract

- add one host-side `GGML_SYCL_MMVQ_Q8_ATTN_SG` selector only to the fused
  attention-triple launcher;
- admit SG4/8/12/16/24/32, with SG8 as the accepted control and invalid values
  falling back to the hardware-derived accepted value;
- keep the exact DP4A2 row body, SG16 reduction, row-to-matrix mapping, model,
  TP split, F16 KV, and every accepted runtime door unchanged;
- announce the selected shape on both devices and require the established
  attention-triple/recurrent-quad fusion census with `VERIFY_MISMATCH=0`;
- run a mirrored same-binary screen before any longer confirmation;
- promote only a repeatable position-balanced gain outside run noise, followed
  by the complete cache-zero endpoint and semantic gates.

This does not cover recurrent-quad SG24 (already accepted), the closed SG4
FFN pair/down arm, or the closed global MMVQ subgroup sweep. It changes only
the distinct fused full-attention Q/V/K launch geometry.

## Result

The same-binary selector announced the exact attention shape
`K5120, N=6144+512+512` on both cards. SG4/8/12/16/24/32 all completed the
mirrored `p64/n256/r1` screen with the accepted recurrent-quad geometry,
non-zero attention-triple census, and `VERIFY_MISMATCH=0`. The short mirror
appeared to favor SG24 at `37.732416` versus `36.818679 tok/s` for SG8
(`+2.482%`), but several modes occupied only one of the host's two known
process timing states.

The longer `p64/n512/r3` SG8-SG24-SG24-SG8 block reversed the apparent gain:

- SG8: `36.821508`, `37.614527`; mean `37.218018 tok/s`;
- SG24: `36.797851`, `37.084880`; mean `36.941366 tok/s`;
- delta: `-0.743%`.

The fully complementary SG24-SG8-SG8-SG24 block crossed in the other
direction:

- SG8: `36.875452`, `36.832927`; mean `36.854190 tok/s`;
- SG24: `37.728818`, `36.822118`; mean `37.275468 tok/s`;
- delta: `+1.143%`.

Across all eight long processes, SG24 averaged `37.108417` versus
`37.036104 tok/s` for SG8, only `+0.195%`. The effect is not repeatable by
order block and is below endpoint-promotion resolution. SG8 remains accepted;
no endpoint or semantic gate was run. Every arm reported zero verifier
mismatches, and no Xe compute fault, reset, timeout, or hang was logged.

Treatment `libggml-sycl.so.0` SHA-256 was
`03a76f137d00945a26498d2b78f4dc680d7364983b8462a2fb52afb2783fd5b1`;
the host `llama-bench` remained
`74e7d48905196285f6e7cd8c8d0b20a8e25cf3f4731b1e2f0f5f6c49ad8d8865`.
Raw evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-attention-triple-sg/`.
