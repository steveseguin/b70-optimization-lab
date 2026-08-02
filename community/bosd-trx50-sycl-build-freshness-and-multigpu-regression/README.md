# SYCL build freshness (+27% decode) & the `-sm layer` multi-GPU regression

**Contributor:** bosd · **Evidence:** `B70-tested` (contributor 2× B70 — see [`STATUS.md`](STATUS.md)).
Raw data: **https://github.com/bosd/trx50-arc-b70-benchmarks**

Two build-version effects found while chasing a single-B70 throughput gap and re-testing multi-GPU across a kernel update. Both on the same 2× Arc Pro B70 / TRX50 host; llama.cpp SYCL (`icx/icpx`, oneAPI 2026.0, `GGML_SYCL_F16=ON`).

## 1. Build freshness is worth ~27% decode (single B70)

Qwen3-30B-A3B-Instruct-2507 UD-Q4_K_XL, `llama-bench -p 512 -n 128`, fa-on:

| llama.cpp build | tg128 | pp512 |
|---|---|---|
| b9455 (Jun 1) | 84.7 | 1287 |
| dee2a84 (Jul 27) | 97.0 | 1383 |
| **11924d4 (Aug 2, master)** | **100.6** | 1393 |

The older Qwen3-30B-A3B Q4_K_M on b9455 was 79 tg/s → newer model/quant ~+7%, **build freshness the other +19%**. ~100 tg/s looks like the current upstream ceiling here. **Takeaway: keep the SYCL build current — it's free throughput.**

## 2. The 2-GPU `-sm layer` crash is a build regression, not the kernel

Qwen3.6-35B-A3B Q8_0 across two B70s (`--device SYCL1,SYCL2 -sm layer`):

| build | kernel 7.0.10 | kernel 7.1.5 |
|---|---|---|
| **b9455** | ✅ works (~26 tg/s — our published Q8 2-GPU numbers) | ✅ works (~26 tg/s) |
| dee2a84 / 11924d4 | ❌ SIGABRT `ggml_backend_tensor_copy` | ❌ same SIGABRT |

Updating the host kernel 7.0.10 → 7.1.5 changed nothing: b9455 works on both, the newer builds crash on both. So the crash is a **regression in `b9455..dee2a84`** on the SYCL device-to-device tensor-copy path — a **build** regression, likely the same class as [#23797](https://github.com/ggml-org/llama.cpp/issues/23797). This gives a **good/bad build window for a `git bisect`**.

**Supporting single-card numbers** (llama-bench, fa-on): gemma-4-26B-A4B UD-Q8_K_XL 26.8 tg/s (B70, base/no-spec); Laguna-XS-2.1 (poolside 30B-A3B coder) Q4_K_M **87.7 (B70) / 72.5 (B60)**.
