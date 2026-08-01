# Q8_0 vs Q4_K_M on the B70 — and what it bounds for FP8

**Contributor:** bosd · **Hardware:** 2× Arc Pro B70 (G31, 32 GB), TRX50 / Threadripper 9960X · **Evidence:** `B70-tested` (contributor hardware — see [`STATUS.md`](STATUS.md)).
Full write-up + raw JSON: **https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/q8-vs-q4-b70.md**

Firmware: BIOS 14.10 · GuC 70.65.0 · kernel 7.0.10 · Mesa 26.0.7. `llama-bench -p 512 -n 128`, SYCL (XMX), Shelly wall power; `t/J(wall) = tg128 ÷ avg W`. GPU-W is the `xe` card energy counter (noisy over the short window → treat wall-W as authoritative).

Motivation: "does the B70 have native FP8?" — no. Battlemage Xe2 **XMX = INT2/4/8, FP16, BF16, TF32; no FP8**. vLLM `--quantization fp8` on B70 is weight-only 8-bit (selects `XPUFP8ScaledMMLinearKernel`, disables `RMSNorm+quant`/`Activation+quant` fusions — "not supported on XPU"). So the honest FP8 proxy is **Q8_0**: same 8 bits, same bandwidth cost.

## Qwen3-30B-A3B (MoE, 3B active)

| Quant | GPUs | Size GiB | pp512 t/s | tg128 t/s | wall W | t/J(wall) |
|---|---|---|---|---|---|---|
| Q4_K_M | 1 | 17.3 | 1227 | **79.2** | 292 | **0.271** |
| Q4_K_M | 2 | 17.3 | 1179 | 77.5 | 327 | 0.237 |
| Q8_0 | 2 | 30.2 | 890 | **41.2** | 311 | **0.132** |

*(Q8_0 30.2 GiB + KV won't fit one 32 GB card → 2-GPU only.)*

## Hermes-4-14B (dense, qwen3)

| Quant | GPUs | Size GiB | pp512 t/s | tg128 t/s | wall W | t/J(wall) |
|---|---|---|---|---|---|---|
| Q4_K_M | 1 | 8.4 | 1393 | **47.5** | 368 | **0.129** |
| Q4_K_M | 2 | 8.4 | 1349 | 47.5 | 422 | 0.113 |
| Q8_0 | 1 | 14.6 | 1464 | **29.8** | 385 | **0.077** |
| Q8_0 | 2 | 14.6 | 1423 | 28.9 | 381 | 0.076 |

## Findings

- **8-bit costs ~half the throughput and ~half the efficiency of Q4.** Qwen3-30B-A3B Q8 = **0.52×** Q4 tg/s (41 vs 79) at **0.49×** t/J; Hermes-14B Q8 = **0.63×** (30 vs 47) at 0.60× t/J. Decode is bandwidth-bound; the tax tracks the ~1.7–2× bytes/weight.
- **FP8 can't beat this.** Same 8-bit weight-only path, no native XMX, fusions disabled → at best the Q8_0 zone, consistent with [#9](https://github.com/steveseguin/b70-optimization-lab/pull/9)'s ~34 tg/s FP8 (27B TP2). FP8's only value on B70 is VRAM/context, never speed — and Q5_K_M/Q6_K already give that at better throughput.
- **MoE beats dense** on speed *and* efficiency: 30B-A3B (3B-act) 79 tg/s vs dense-14B 47, at 2× the t/J. Buy active-params, not total-params.
- **Two GPUs never help a fits-on-one model.** Hermes tg identical 1↔2 GPU at higher power; Qwen Q4 slightly worse on 2. `-sm layer` serialises — reserve dual-B70 for models that don't fit.
- **Prefill is quant-insensitive** (~1200–1460 pp t/s, compute-bound).

**Bottom line:** Q4_K_M is the serving default; 8-bit (Q8_0 *or* FP8) is a ~2×-cost quality-ceiling point, and on B70 Q8_0-SYCL is the mature way to get it, not FP8.
