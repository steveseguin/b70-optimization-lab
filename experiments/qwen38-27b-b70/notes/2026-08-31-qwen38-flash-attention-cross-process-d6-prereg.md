# Qwen3.8 paged FlashAttention cross-process D6 preregistration

Date: 2026-08-31

Status: **preregistered before D6 operator calls**

## Question

The same four realistic prompts branch across both the official Triton-GDN
parent and the current native-GDN candidate. Are the shared paged-KV insertion
and FA2 full-attention paths bitwise unstable across fresh processes?

## Frozen diagnostic

- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0 and four fresh containers;
- Qwen full-attention dimensions: 24 query heads, 4 KV heads, head dimension
  256, FP16, scale 0.0625, causal FA2, paged KV with block size 64;
- every actual strict-suite prefill length: 48, 49, 52, 53, 55, 56, 57, 59,
  65, 71, 75, and 78 tokens;
- for each length, four identical prefill repetitions using production
  `reshape_and_cache_flash` followed by paged `flash_attn_varlen_func`;
- for each length, a fresh fixed cache followed by 32 fixed M=1 recurrent KV
  inserts and decode-attention calls; hash complete caches and outputs;
- all Q/K/V inputs generated deterministically on CPU before transfer.

Any multiple hash for an identical case is a positive causal finding. One
hash for every case is negative evidence only. This operator diagnostic cannot
promote a model rate or authorize MTP.
