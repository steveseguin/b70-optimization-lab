# Qwen3.8 27B Q8 TP2 attention-triple workgroup sweep

Date: 2026-08-17

Status: active; claimed by the ASRock two-B70 host.

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
