# SYCL build freshness (+27% single-B70 decode) and the `-sm layer` multi-GPU regression (b9455→dee2a84)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` (on contributor's 2× B70, not the reference lab) |
| Patch review status | n/a — benchmark + bisect, no source patch |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until re-run in the reference lab |

## Provenance

- Contributor: **bosd** (`github.com/bosd`)
- Source PR or URL: this PR; raw data in `bosd/trx50-arc-b70-benchmarks`
- Commits under test: llama.cpp **`b9455`** (Jun 1), **`dee2a84`** (Jul 27), **`11924d4`** (Aug 2, master) — all SYCL, `icx/icpx` oneAPI 2026.0, `-DGGML_SYCL=ON -DGGML_SYCL_F16=ON`, Release
- Right-to-submit statement present: yes
- Third-party material and attribution: none

## Claim

Two build-version effects on the same 2× B70 hardware: **(1)** single-GPU decode of Qwen3-30B-A3B-2507 rises **79 → 100.6 tg/s (+27%) purely from newer llama.cpp builds**; **(2)** the 2-GPU `-sm layer` `ggml_backend_tensor_copy` SIGABRT is a **regression between `b9455` and `dee2a84`**, reproducible on **both** kernel 7.0.10 and 7.1.5 — i.e. it is a build regression, not kernel-gated.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel **Arc Pro B70** (Battlemage G31, `8086:e223`, 32 GB) + 1× B60 (24 GB), ASRock TRX50 WS, Threadripper 9960X |
| OS / kernel | Fedora Server 44; tested on **kernel 7.0.10** and **7.1.5** |
| GPU driver (`i915`/`xe`) and version | **`xe`** |
| compute-runtime / level-zero | NEO **26.18.38308.1** |
| Engine / image and exact version | llama.cpp SYCL, oneAPI 2026.0; commits **b9455 / dee2a84 / 11924d4** |
| Model repo and revision | Qwen3-30B-A3B-Instruct-2507 (UD-Q4_K_XL); Qwen3.6-35B-A3B (Q8_0, MTP-GGUF) for the 2-GPU test |
| Quantization (weights / KV / activations) | UD-Q4_K_XL / Q8_0; KV f16; no activation quant |
| Command and environment variables | single-GPU: `llama-bench -p 512 -n 128 -sm none -mg 1 -fa 0,1`; 2-GPU: `llama-cli --device SYCL1,SYCL2 -sm layer -ngl 99 -fa 0`; `GGML_SYCL_DISABLE_OPT=1` |
| Prompt / output / context lengths, concurrency | pp512 / tg128; concurrency 1 |
| Cache and speculation policy | cold, `llama-bench` defaults; no speculation |
| Metric definition, repeats, dispersion, TTFT | tg128 & pp512 t/s (llama-bench default 5 repeats); TTFT n/a |
| Logs / JSON / durable links | https://github.com/bosd/trx50-arc-b70-benchmarks |

## Reference Lab Environment

Nothing executed in the reference lab — contributor's 2× B70.

## What Was Actually Run Here

`llama-bench` single-GPU across the three build commits; and a `llama-cli --device SYCL1,SYCL2 -sm layer` generation on each build across two kernels, watching for the crash.

## Findings

**(1) Build freshness — Qwen3-30B-A3B-Instruct-2507 UD-Q4_K_XL, single B70, `-p 512 -n 128`, fa-on:**

| build | tg128 | pp512 |
| --- | --- | --- |
| b9455 (Jun 1) | 84.7 | 1287 |
| dee2a84 (Jul 27) | 97.0 | 1383 |
| **11924d4 (Aug 2 master)** | **100.6** | 1393 |

Older Qwen3-30B-A3B Q4_K_M on b9455 was 79 → so model/quant added ~+7%, **build freshness the other +19%**. 100.6 appears to be the current upstream ceiling for this config.

**(2) `-sm layer` 2-GPU regression — Qwen3.6-35B-A3B Q8_0, two B70s:**

| build | kernel 7.0.10 | kernel 7.1.5 |
| --- | --- | --- |
| **b9455** | ✅ works (~26 tg/s, our published Q8 2-GPU numbers) | ✅ works (~26 tg/s) |
| dee2a84 / 11924d4 | ❌ SIGABRT `ggml_backend_tensor_copy` (first decode) | ❌ same SIGABRT |

The crash is a **regression in the window `b9455..dee2a84`**, on the SYCL `-sm layer` device-to-device tensor-copy path, **independent of kernel** (fails on both 7.0.10 and 7.1.5; b9455 works on both). Likely the same class as **[ggml-org/llama.cpp#23797](https://github.com/ggml-org/llama.cpp/issues/23797)** — this narrows a good-vs-bad build window for a bisect.

**Supporting single-card numbers (llama-bench, fa-on):** gemma-4-26B-A4B UD-Q8_K_XL = 26.8 tg/s (B70, b9455, base/no-spec); Laguna-XS-2.1 (poolside 30B-A3B) Q4_K_M = **87.7 (B70) / 72.5 (B60)** on 11924d4.

## Known Issues

None found — measurement + bisect, no source to review.

## Open Questions For The Contributor

To raise to `B70-verified`: reference-lab re-run confirming (a) the ~100 tg/s single-B70 ceiling on a current build, and (b) that `-sm layer` works on a b9455-era build but SIGABRTs on a current build. A `git bisect` in the `b9455..dee2a84` window would pin the exact regressing commit for #23797.

## Disposition

Stays `community/` as `B70-tested`. Most useful immediately as **#23797 bisect input** (good/bad build window) and as a "keep your SYCL build current" data point (+27% for free).
