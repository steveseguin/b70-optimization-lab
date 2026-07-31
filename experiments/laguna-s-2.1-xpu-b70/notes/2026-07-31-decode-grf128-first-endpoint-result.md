# Laguna decode GRF128 first endpoint result

Date: 2026-07-31 America/Toronto

Status: **valid first cold candidate leg; provisional new best pending one
same-identity confirmation**.

## Result

The preregistered decode-only 128-GRF grouped-GEMM candidate passed every
frozen endpoint gate:

- historical 100-event compatibility metric:
  **`121.29932116191253 tok/s`**;
- conventional 99-inter-token-interval metric:
  **`120.0863279502934 tok/s`**;
- 13/13 canonical-q1 token-ID and output-text hashes equal;
- `cached_tokens=0` on all 13 unique prompts, each invoked once;
- target capture/replay topology 146/145 on all four ranks;
- draft capture/replay topology 14/13 on all four ranks;
- no warmup generation or retry;
- graceful worker shutdown, free port, and 72-second pre/post idle gates.

Artifact root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-decode-grf128-scored-20260731T0931Z
```

Relative to the matched `121.03724088473012` / `119.82686847588282`
incumbent, the first leg is `+0.2165%` under both accounting formulas. This is
a real valid measurement, but the margin is smaller than the observed host
noise. It is therefore recorded as a provisional new best, not yet promoted
or submitted. One fresh same-identity confirmation is required before deciding
whether the candidate is a reproducible record.

## Exact identity

- target: `poolside/Laguna-S-2.1-INT4`, local release manifest
  `c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e`;
- draft: `poolside/Laguna-S-2.1-DFlash-INT4`;
- BF16 KV, TP4/EP4, one active generation;
- exact verifier width 12 and DFlash depth 11;
- vLLM `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU kernels `e4163f93574326b2772742e0f51372a5a3777aa5`;
- grouped-GEMM DSO SHA-256
  `df2f63a04630c3b50d3ffe2d61db3e3d68914436ba14270dcc45ddfec6b3467f`;
- runtime lock SHA-256
  `4207f80d96b4219aa48b4d71f2d59333c1d77c942127b5c325c7107853dcb3b4`;
- `VLLM_XPU_LAGUNA_DECODE_GRF128=1`, scale-vector on, dequant-MAD and
  scale-fold off, prefetch distance 6;
- segmented DFlash graph and inline DFlash attention on; target-inline
  gathers and replicated embedding off.

The source patch is
`patches/laguna-s-2.1-xpu-b70/0001-laguna-add-exact-decode-GRF128-kernel.patch`
(SHA-256 `f4a4cfa61d47526d02586822f8c00a6e983062737df79e4e141675ae91bc32c0`).
The complete source-history bundle is
`patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-decode-grf128-e4163f9-20260731.bundle`
(SHA-256 `e21141feecf16de832ca841b0046c8ea523113795498c392ddc91c08833a5596`).
The measured DSO is preserved at
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-decode-grf128-build-e4163f9-20260731T0918Z/libgrouped_gemm_xe_2.so`.

## Interpretation and next seam

The direct component gate showed `1.0071x` on W13 and `1.0332x` on W2, while
the endpoint moved only `0.22%`. Raising occupancy alone is therefore useful
but not a route to 130 tok/s.

The stronger follow-up is a separate, fail-closed exact-decode kernel that
instantiates only the live `SCALE_VEC=1`, `DEQUANT_MAD=0`, `SCALE_FOLD=0`
mainloop at compile time. The current production kernel still carries several
runtime-selected mainloop bodies and their dispatch plumbing in the device
binary. Static specialization may remove materially more instructions and
register pressure while preserving the exact arithmetic sequence. It must
first pass an ISA/code-size screen, then the existing raw-BF16 component gate,
and only then an endpoint leg.

