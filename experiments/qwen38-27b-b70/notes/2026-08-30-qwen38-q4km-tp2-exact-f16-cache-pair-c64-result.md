# Qwen3.8-27B Q4_K_M TP2 exact F16 cache pair: qualified c64 result

Caching two exact projection families raises the qualified two-B70 c64 result
to **`175.623794 tok/s`**. Fresh candidates measured `175.798577` and
`175.449010 tok/s`; both matched the frozen 64-request batch oracle 64/64,
all cached-token counts were zero, no cross-base response collision occurred,
kernel-error evidence was empty, and both servers shut down cleanly.

This is `+4.45%` over the prior single-family `168.138940 tok/s` result and
`+9.10%` over its same-binary cache-off controls centered at
`160.981046 tok/s`. The two candidate rates differ by only `0.199%`.

## Exact mechanism and boundary

The default-off cache retains the same F16 bytes produced by the incumbent
Q4_K dequantizer for both `ffn_down` and `ffn_gate`, per device. The unchanged
oneDNN GEMM consumes those bytes. A small allocation-free comma-list parser is
the only source increment over the already-qualified one-filter implementation:

```bash
export GGML_SYCL_Q4K_F16_CACHE_FILTER=ffn_down,ffn_gate
```

This trades device memory for batched throughput: approximately 13 GiB of
additional memory per B70. Exact peak VRAM still needs a dedicated capture
before this becomes a broad service default. It remains an aggregate-only
result; the cache does not accelerate the one-user MMVQ route, so the
`49.717503 tok/s` one-user headline is unchanged.

The fixed c64 cohort uses eight distinct short operational prompts, expanded
with unique validation-case suffixes. It is a capacity-and-output-identity
profile, not a replacement for the independent varied natural/code single-user
suite. No rate is transferred to another concurrency, context, quantization,
card count, MTP depth, or prompt shape.

## Evidence

- [Preregistration](../data/2026-08-30-qwen38-q4km-tp2-exact-cache-pair-r10-prereg.json)
- [Structured result](../data/2026-08-30-qwen38-q4km-tp2-exact-cache-pair-r10-results.json)
- [Comma-filter source increment](../patches/llama-qwen38-q4k-f16-cache-comma-filter-20260830.patch)
- [Base exact-cache patch](../patches/llama-qwen38-q4k-f16-exact-weight-cache-candidate-20260830.patch)
- [Strict runner](../scripts/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh)

The individual `ffn_gate` and `ffn_up` screens were output-exact but slower
than the preregistered advancement threshold. They remain negative evidence in
[the r9 result](../data/2026-08-30-qwen38-q4km-tp2-exact-cache-tensor-screen-r9-results.json),
not alternative records.
