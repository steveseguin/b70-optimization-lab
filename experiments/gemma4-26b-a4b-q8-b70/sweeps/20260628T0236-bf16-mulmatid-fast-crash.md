# 2026-06-28T0236 - BF16 MUL_MAT_ID multi-token fast path crashed

Goal: crack a reliable 100 tok/s strict fresh-response headline for
Gemma 4 26B A4B IT UD-Q8_K_XL on one B70 by attacking the current node-profile
hotspot: final-layer BF16 verifier MoE gate/up (`ffn_moe_gate_up-29`).

Patch tried in `/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- added default-off `LLAMA_SYCL_MUL_MAT_ID_BF16_MULTI_TOKEN_FAST=1`;
- added a direct BF16 multi-token `MUL_MAT_ID` SYCL kernel for
  `src1=[ncols,1,n_tokens]`, `ids=[n_experts_used,n_tokens]`, `n_tokens<=8`;
- made BF16 `MUL_MAT_ID` graph-eligible under that env.

Strict A/B screen, stamp `20260628T023623Z`:

- control GPU0:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-controlA-n3-nmin2-p00475-ub1024-20260628T023623Z/summary.json`
  passed, median100 `98.0865`, p10 `89.5469`, full128 `94.1577`.
- control GPU2:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-controlB-n3-nmin2-p00475-ub1024-20260628T023623Z/summary.json`
  passed, median100 `95.0091`, p10 `87.1717`, full128 `91.9284`.
- BF16-fast GPU1:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bf16fastA-n3-nmin2-p00475-ub1024-20260628T023623Z/`
  failed before readiness.
- BF16-fast GPU3:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bf16fastB-n3-nmin2-p00475-ub1024-20260628T023623Z/`
  failed before readiness.

Crash signature on both BF16 lanes:

```text
SYCL error: CHECK_TRY_ERROR( stream->memcpy(ids_host.data(), ids_dev, ids_nbytes))
  in function operator() at ggml/src/ggml-sycl/ggml-sycl.cpp:7175
```

Diagnostics:

- Restricting the global multi-token name filter to `ffn_moe_gate_up-29`
  (`gemma4-q8-gpu1-bf16fast-filter29-smoke-20260628T023847Z`) still aborted
  before readiness with the same `ids_host` copy failure.
- A graph-off diagnostic
  (`gemma4-q8-gpu1-bf16fast-graphoff-smoke-20260628T023953Z`) also aborted
  before readiness. The backtrace still entered `ggml_backend_sycl_graph_compute`,
  but the practical result is unchanged: this code path is not safe enough to
  keep pursuing as a quick record candidate.

Decision:

- Negative. No valid BF16-fast throughput result exists.
- The source-level BF16 fast-path additions were reverted immediately after the
  crash. Do not set `LLAMA_SYCL_MUL_MAT_ID_BF16_MULTI_TOKEN_FAST`; it was an
  experiment-only env and is not part of the promoted stack.
- This does not affect the current best record stack, which remains the VDR2 /
  Q8 reorder / p021 small-ncols / MTP stack.

Implication:

The final BF16 layer is a real hotspot, but a standalone direct BF16
`MUL_MAT_ID` kernel is not a quick path to reliable `>100`. A safer future
approach would start with a CPU/GPU correctness harness or a debug build that
waits immediately after the BF16 kernel, rather than testing inside the full
server warmup path.
