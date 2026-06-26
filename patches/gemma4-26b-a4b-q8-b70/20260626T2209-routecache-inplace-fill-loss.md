# 2026-06-26T22:09Z Gemma4 Q8 route-cache in-place fill loss

## Intent

Test a narrow `MUL_MAT_ID` route-cache metadata optimization without changing
the tuned math path. The current record already uses
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, which fills a one-shot host route cache
on the gate/up op and reuses it for the immediately following down op. The
miss path still builds local host vectors and then copies them into the cache.

This patch adds a default-off flag:

```text
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1
```

When enabled on a route-cache miss, the generic `ggml_sycl_mul_mat_id()` path
fills `route_cache.ids_host`, `route_cache.expert_row_counts`,
`route_cache.expert_row_offsets`, and `route_cache.routed_row_src` directly,
then points the current op at that cache storage. One-shot validity and the
existing route-cache hit/clear behavior are unchanged.

## Source delta

File:
`/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`

Patch shape:

- add forward declaration:
  `static bool ggml_sycl_mul_mat_id_route_cache_inplace_enabled();`
- add env parser beside `ggml_sycl_mul_mat_id_route_cache_enabled()`;
- in `ggml_sycl_mul_mat_id()` generic multi-token path:
  - compute `use_route_cache_inplace = use_route_cache && env_enabled`;
  - on cache miss with in-place enabled, copy device `ids` directly into
    `route_cache.ids_host`, wait, run `mmid_counting_sort_rows()` directly into
    cache vectors, and point the current op's route pointers at those vectors;
  - skip the old local-vector-to-cache assignments when in-place fill was used.

Harness logging added:

- `scripts/run-gemma4-26b-first-baseline.sh`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh`.

## Result

Run:
`data/gemma4-q8-gpu2-routecache-inplace-screen-20260626T220930Z/summary.json`

Identity:

- Q8 target:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Q4_0 MTP draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU2, `CTX_SIZE=8192`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
  `POLL=100`, flash attention off, graph on, VMM off
- current record recipe plus:
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1`

Validation:

- canary: `128` repeats / `512` rows, pass
- cached-token validity: `[0, 0, 0]`, all zero
- fresh row0 after-TTFT throughput: `101.52759496160394 tok/s`
- support mean after-TTFT throughput: `102.83917018605882 tok/s`
- support max after-TTFT throughput: `103.50911695639134 tok/s`
- current valid record: `103.51547512013657 tok/s` fresh row0

## Decision

Reject / do not promote / do not submit to LocalMaxxing.

The patch is correctness-clean but does not produce a fresh-response headline
win. Later support rows reach the old record within noise, but the fresh row0
claim is below the current validated record. This confirms the remaining
route-cache host-vector copy is not a meaningful bottleneck for the current
Q8/MTP recipe.

Keep the env-gated source patch as a durable experiment artifact, but leave it
off in promoted recipes. The next credible Gemma lanes are larger verifier-side
changes, especially a small-token Gemma4/Q8 verifier MoE boundary or a better
target LM-head top-1 kernel, not another route-cache metadata tweak.
