# 2026-07-01 Global Causal Fast-Mask Long-Context Negative
## Decision
Closed negative / noise. The default-off global-attention causal fast-mask patch passed canaries and exact long-context gates, but did not improve validated prefill after GPU crossover. Preserve the patch for reference, but do not promote it or leave it active in the working source.
## Why Tried
Profiles showed long prompt processing dominated by global `FLASH_ATTN_EXT` calls. The idea was to skip F16 causal mask loads for K tiles that are fully valid for all Q columns in a global causal prefill workgroup, while keeping normal masking for boundaries, SWA, ALiBi, decode, and unsupported shapes.
## Source Artifacts
- Pre-experiment active source snapshot: `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-active-record-stack-before-fastmask-source.patch`
- Post-experiment source snapshot: `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-global-fattn-causal-fastmask-source.patch`
- Diffstat: `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-global-fattn-causal-fastmask-source.diffstat`

The final tested version tightened an initially over-broad mask skip. It only skipped mask loads when the whole K tile was valid for the earliest Q column in the workgroup: `k_VKQ_0 + nbatch_fa <= q_abs_min + 1`.
## Validation Setup
- Model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` target/verifier, Q4_0 MTP draft.
- Runtime: rebuilt llama.cpp `c926ad098` Gemma record stack, one B70 per lane.
- Long service identity: `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`, `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`, SWA left-bound enabled with min Q 2048.
- Candidate flags: `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK=1`, `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK_MIN_Q=2048`.
- Cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`; each prompt once, `cached_tokens=0`, exact JSON validation.
- Canaries: 8 repeats per lane, 32 rows per lane.
## Results
| round | variant | gpu | median prefill tok/s | mean prefill tok/s | median decode tok/s | canary | long gate | label |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ab1 | control | gpu0 | 1106.326 | 1101.742 | 119.220 | 32/32 pass | pass | `data/gemma4-q8-gpu0-longctx-fastmask-control-ub2048-20260701Tfastmask-ab1/summary.json` |
| ab1 | fastmask | gpu1 | 1087.637 | 1085.050 | 119.073 | 32/32 pass | pass | `data/gemma4-q8-gpu1-longctx-fastmask-on-ub2048-20260701Tfastmask-ab1/summary.json` |
| ab2 | fastmask | gpu0 | 1106.006 | 1103.131 | 119.253 | 32/32 pass | pass | `data/gemma4-q8-gpu0-longctx-fastmask-on-ub2048-20260701Tfastmask-ab2/summary.json` |
| ab2 | control | gpu1 | 1086.281 | 1083.330 | 119.076 | 32/32 pass | pass | `data/gemma4-q8-gpu1-longctx-fastmask-control-ub2048-20260701Tfastmask-ab2/summary.json` |

- AB1 delta: `-1.689%` fast-mask vs control.
- AB2 crossover delta: `+1.816%` fast-mask vs control.
- Crossover average: control `1096.304` median prefill tok/s, fast-mask `1096.821` median prefill tok/s, delta `+0.047%`.

Per-case rows:

### gemma4-q8-gpu0-longctx-fastmask-control-ub2048-20260701Tfastmask-ab1

| case | prompt tokens | prefill tok/s | decode tok/s | TTFT s | cached_tokens | exact pass |
|---|---:|---:|---:|---:|---:|---:|
| lc-12288-early | 16213 | 1201.333 | 126.898 | 13.496 | 0 | True |
| lc-16384-late | 22730 | 1106.326 | 119.220 | 20.545 | 0 | True |
| lc-22000-middle | 30400 | 997.565 | 112.273 | 30.474 | 0 | True |

### gemma4-q8-gpu1-longctx-fastmask-on-ub2048-20260701Tfastmask-ab1

| case | prompt tokens | prefill tok/s | decode tok/s | TTFT s | cached_tokens | exact pass |
|---|---:|---:|---:|---:|---:|---:|
| lc-12288-early | 16213 | 1184.301 | 126.467 | 13.690 | 0 | True |
| lc-16384-late | 22730 | 1087.637 | 119.073 | 20.899 | 0 | True |
| lc-22000-middle | 30400 | 983.214 | 111.949 | 30.919 | 0 | True |

### gemma4-q8-gpu0-longctx-fastmask-on-ub2048-20260701Tfastmask-ab2

| case | prompt tokens | prefill tok/s | decode tok/s | TTFT s | cached_tokens | exact pass |
|---|---:|---:|---:|---:|---:|---:|
| lc-12288-early | 16213 | 1204.612 | 126.753 | 13.459 | 0 | True |
| lc-16384-late | 22730 | 1106.006 | 119.253 | 20.551 | 0 | True |
| lc-22000-middle | 30400 | 998.776 | 112.302 | 30.437 | 0 | True |

### gemma4-q8-gpu1-longctx-fastmask-control-ub2048-20260701Tfastmask-ab2

| case | prompt tokens | prefill tok/s | decode tok/s | TTFT s | cached_tokens | exact pass |
|---|---:|---:|---:|---:|---:|---:|
| lc-12288-early | 16213 | 1183.264 | 126.395 | 13.702 | 0 | True |
| lc-16384-late | 22730 | 1086.281 | 119.076 | 20.925 | 0 | True |
| lc-22000-middle | 30400 | 980.445 | 111.860 | 31.006 | 0 | True |

## Follow-Up
Do not run the short-decode guard for this patch because the service/prefill crossover did not show a real improvement. Restore the active source to the pre-fastmask record stack before starting the next lane.
