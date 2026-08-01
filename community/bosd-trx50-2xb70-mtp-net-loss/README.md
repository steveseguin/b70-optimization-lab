# MTP speculative decoding on the B70 — a net loss for single-stream decode

**Contributor:** bosd · **Evidence:** `B70-tested` (contributor B70; AMD rows are dominick253's — see [`STATUS.md`](STATUS.md)).
Full write-up: **https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/mtp-spec-decode-b70.md**

Model: **Qwen3.6-35B-A3B UD-Q4_K_M** from [`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) (MTP variant — carries `blk.40.nextn.*`; the base repo drops it). **Single B70**, `llama-server` (upstream `dee2a84`, oneAPI 2026.0, SYCL), `n_predict=512`, temp 0, `--spec-draft-n-max 3`. Wall power via Shelly.

## Result

| Flash-attn | MTP-off tok/s | MTP-on tok/s | MTP effect | draft acceptance |
|---|---|---|---|---|
| off (`-fa 0`) | **72.4** | 68.6 | **−5%** | 71% (348/487), mean len 3.13 |
| on (`-fa 1`)  | **72.6** | 65.1 | **−10%** | 66% (339/515), mean len 2.97 |

MTP engages correctly (~70% acceptance, mean draft len ~3) — but **MTP-on is consistently slower**, and flash-attn makes it worse.

## Why MTP loses here (MoE + bandwidth-bound)

Single-stream decode on the B70 is memory-bandwidth-bound. Speculative decoding trades compute for a batched verification pass — a win only if verifying K draft tokens is ~as cheap as one. On a **3B-active MoE**, a batch of 3–4 draft tokens routes to **more experts**, so the verification reads **more weight bandwidth**, cancelling the batching benefit — and the MTP draft head adds forward-pass overhead. Net −5 to −10%. Q4/1-GPU is the best case; Q8_K_XL or 2-GPU is more bandwidth-bound.

## Context — supplies the MTP-off baseline PR #14 lacked

[PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14) (dominick253) reported ~40 tok/s *with* MTP (Q8_K_XL, 2× B70, kernel 7.0.0), 86.5% acceptance, but **no MTP-off control**. High acceptance ≠ speedup. dominick253 then re-ran his own config and measured **MTP-off ≈ 45 vs MTP-on ≈ 40** — a net loss on Q8/2-GPU too, matching this Q4/1-GPU result.

## Cross-arch: MTP *helps* on AMD, *hurts* on Intel — it's the backend, not the hardware

Same model on **2× AMD Radeon 7800 XT (ROCm)** (credit: dominick253):

| Rig | backend | MTP-off | MTP-on | effect |
|---|---|---|---|---|
| Intel Arc B70 | SYCL | 72 | 68 | **−5%** |
| AMD 7800 XT ×2 | ROCm/HIP | ~70 | ~100 | **+43%** |

The **MTP-off baselines are ~identical** (72 vs ~70) — raw decode is the same — but the **MTP path** is +43% on ROCm and −5% on SYCL. So it's the **llama.cpp SYCL batched draft-verification path being immature**, not B70 memory bandwidth.

**Takeaway:** don't enable MTP for single-stream MoE serving on B70 *today*; it costs throughput. It's not a hardware dead-end — re-test after SYCL kernel/oneAPI updates. Upstream: [#23533](https://github.com/ggml-org/llama.cpp/issues/23533) (overhead shrinking build-over-build), [#23797](https://github.com/ggml-org/llama.cpp/issues/23797) (multi-GPU). ⚠️ `dee2a84` is a known-good build (avoid the #24795 MTP-load regression in b9702/b9717).
