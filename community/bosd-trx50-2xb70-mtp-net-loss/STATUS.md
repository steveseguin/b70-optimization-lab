# MTP speculative decoding on B70 — net loss for single-stream MoE decode

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` (on contributor's B70, **not** the reference lab → not `B70-verified`) |
| Patch review status | n/a — benchmark result, no source patch |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until re-run in the reference lab |

## Provenance

- Contributor: **bosd** (`github.com/bosd`)
- Source PR or URL: consolidates findings from [PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14); full data in `bosd/trx50-arc-b70-benchmarks`
- Commits: upstream llama.cpp **`dee2a84`** (MTP-capable SYCL build, oneAPI 2026.0)
- Right-to-submit statement present: yes — own measurements
- Third-party material and attribution: **AMD 7800 XT cross-arch numbers and the Q8_K_XL/2× B70 MTP-on figure are dominick253's** (PR #14), reproduced here with credit

## Claim

With MTP genuinely engaged (~70% draft acceptance), **MTP-on is 5–10% *slower* than MTP-off** for single-stream decode of a 3B-active MoE on the B70 — and the same model shows **+43% on 2× AMD 7800 XT (ROCm)**, so the deficit is the **SYCL backend's batched-verification path, not B70 hardware**.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 1× **Arc Pro B70** (Battlemage G31, `8086:e223`, 32 GB), TRX50 / Threadripper 9960X |
| OS / kernel | Fedora Server 44, kernel **7.0.10** |
| GPU driver (`i915`/`xe`) and version | **`xe`** |
| compute-runtime / level-zero | NEO **26.18.38308.1** |
| Engine / image and exact version | upstream **llama.cpp `dee2a84`** `llama-server`, **SYCL**, oneAPI **2026.0** |
| Model repo and revision | **`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`** UD-Q4_K_M (the **MTP variant** — carries `blk.40.nextn.*`; the base `-GGUF` repo drops it) |
| Quantization (weights / KV / activations) | weights UD-Q4_K_M; KV f16; no activation quant |
| Command and environment variables | `llama-server` `--spec-type draft-mtp --spec-draft-n-max 3`, `n_predict=512`, temp 0; `-fa 0` and `-fa 1`; `GGML_SYCL_DISABLE_OPT=1`; single GPU |
| Prompt / output / context lengths, concurrency | n_predict 512; **concurrency 1** (single-stream) |
| Cache and speculation policy | cold; **MTP draft head, `--spec-draft-n-max 3`** (vs MTP-off control) |
| Metric definition, repeats, dispersion, TTFT | decode tok/s (server telemetry) MTP-off vs MTP-on; draft acceptance % + mean draft length reported; `t/J = tok/s ÷ wall W` (Shelly) |
| Logs / JSON / durable links | https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/mtp-spec-decode-b70.md (+ `bench-mtp-1gpu.sh`) |

## Reference Lab Environment

Nothing executed in the reference lab — contributor submission on the contributor's B70.

## What Was Actually Run Here

Nothing in the reference lab. The Intel B70 rows are the contributor's measurements; the AMD 7800 XT rows and the Q8_K_XL/2-GPU MTP-on figure are **dominick253's** (PR #14), included for the cross-arch comparison with credit.

## Findings

**Confirmed (contributor B70, Q4/1-GPU):**

| Flash-attn | MTP-off tok/s | MTP-on tok/s | effect | acceptance |
|---|---|---|---|---|
| off (`-fa 0`) | **72.4** | 68.6 | **−5%** | 71%, mean len 3.13 |
| on (`-fa 1`) | **72.6** | 65.1 | **−10%** | 66%, mean len 2.97 |

- MTP engages correctly (~70% acceptance) but **loses**: a 3B-active MoE's batched draft-verification routes to **more experts** → more weight-bandwidth on bandwidth-bound decode, cancelling the batching win; the draft head adds overhead. This Q4/1-GPU config is MTP's best case here (Q8/2-GPU is more bandwidth-bound).
- **Supplies the MTP-off baseline that PR #14 lacked.** High acceptance ≠ speedup.
- **Cross-arch (same model, credit dominick253):** Intel B70/SYCL **−5%** vs AMD 7800 XT×2/ROCm **+43%**, with **matching MTP-off baselines (~72 vs ~70)** — so the divergence is the SYCL backend, not the hardware.

**Hypothesis (not yet reproduced here):** MTP should flip positive on B70 once the SYCL MoE/spec-decode kernels mature. Tracking [ggml-org/llama.cpp#23533](https://github.com/ggml-org/llama.cpp/issues/23533) (SYCL MTP no-speedup — overhead shrinking build-over-build: −21%/−34% on b9292 → −5% on dee2a84) and [#23797](https://github.com/ggml-org/llama.cpp/issues/23797) (SYCL multi-GPU tensor-split). ⚠️ #24795 is a *newer* MTP-load regression (b9702/b9717) — `dee2a84` is a known-good build.

## Known Issues

None found — result-only submission.

## Open Questions For The Contributor

To raise to `B70-verified`: reference-lab re-run of `bench-mtp-1gpu.sh` (Qwen3.6-35B-A3B-MTP-GGUF UD-Q4_K_M, single B70) confirming MTP-on < MTP-off on the reference kernel/runtime.

## Disposition

Stays `community/` as `B70-tested`. Actionable now as a **negative result**: don't enable MTP for single-stream MoE serving on B70 today; re-test after SYCL backend/oneAPI bumps (the overhead is trending toward break-even).
