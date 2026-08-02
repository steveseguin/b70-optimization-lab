# Q8_0 vs Q4_K_M cost on 2× B70 (and the ceiling it puts on FP8)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` (on contributor's 2× B70, **not** the reference lab → not `B70-verified`) |
| Patch review status | n/a — benchmark result, no source patch |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until re-run in the reference lab |

## Provenance

- Contributor: **bosd** (`github.com/bosd`)
- Source PR or URL: this PR; full data + raw JSON in `bosd/trx50-arc-b70-benchmarks`
- Commits: llama.cpp **SYCL** build (`build-sycl`, `icx/icpx`, oneAPI 2026.0, `-DGGML_SYCL_F16=ON`); exact upstream commit not pinned in notes → `unknown`
- Right-to-submit statement present: yes — own measurements, Unlicense-compatible
- Third-party material and attribution: none

## Claim

On 2× Arc Pro B70, **Q8_0 delivers ~0.5–0.6× the decode throughput and ~0.5–0.6× the tokens/joule of Q4_K_M** (Qwen3-30B-A3B: 41.2 vs 79.2 tg/s; Hermes-4-14B: 29.8 vs 47.5 tg/s), which bounds weight-only FP8 on B70 to at best the Q8_0 operating point.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel **Arc Pro B70** (Battlemage G31, `8086:e223`, 32 GB) on ASRock TRX50 WS, Threadripper 9960X (24c/48t) |
| OS / kernel | Fedora Server 44, kernel **7.0.10** |
| GPU driver (`i915`/`xe`) and version | **`xe`** |
| compute-runtime / level-zero | NEO **26.18.38308.1** |
| Engine / image and exact version | llama.cpp **SYCL** `llama-bench`, oneAPI 2026.0, `-DGGML_SYCL_F16=ON`; commit `unknown` (see linked repo) |
| Model repo and revision | Qwen3-30B-A3B (MoE 3B-act) and Hermes-4-14B (dense, qwen3), Q4_K_M + Q8_0 GGUFs |
| Quantization (weights / KV / activations) | weights **Q4_K_M / Q8_0**; KV f16; no activation quant |
| Command and environment variables | `llama-bench -p 512 -n 128`; `GGML_SYCL_DISABLE_OPT=1`; 1-GPU vs 2-GPU `-sm layer` |
| Prompt / output / context lengths, concurrency | pp512 / tg128; **concurrency 1** (single-stream) |
| Cache and speculation policy | cold, `llama-bench` defaults; no speculative decoding |
| Metric definition, repeats, dispersion, TTFT | tg128 & pp512 t/s (llama-bench default 5 repeats); `t/J(wall) = tg128 ÷ avg wall W` via **Shelly Plug S Gen3**; GPU-W (xe counter) noisy over the short window → wall-W authoritative; TTFT n/a |
| Logs / JSON / durable links | https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/q8-vs-q4-b70.md (+ `raw/`, `bench-q8q4.sh`) |

## Reference Lab Environment

Nothing executed in the reference lab — this is a contributor submission measured on the contributor's own 2× B70.

## What Was Actually Run Here

Nothing in the reference lab. All numbers are from the contributor's TRX50 host (above), `llama-bench` with Shelly wall-power sampling; scripts and raw JSON linked.

## Findings

- **8-bit costs ~2× vs Q4** on both models: Qwen3-30B-A3B Q8 = 0.52× Q4 tg/s at 0.49× t/J; Hermes-4-14B Q8 = 0.63× Q4 tg/s at 0.60× t/J. Decode is bandwidth-bound; the slowdown tracks the ~1.7–2× bytes/weight.
- **This bounds FP8 on B70.** Battlemage Xe2 XMX has **no native FP8** (INT2/4/8, FP16, BF16, TF32 only), so vLLM FP8 is weight-only (`XPUFP8ScaledMMLinearKernel`, RMSNorm/Activation fusions disabled). FP8 therefore lands at best in the Q8_0 zone — consistent with PR #9's ~34 tg/s FP8. **FP8's only value on B70 is VRAM/context, not speed.**
- **MoE beats dense** on speed and efficiency (30B-A3B 79 tg/s > dense 14B 47). **2 GPUs never help a fits-on-one model** (`-sm layer` serialises; identical or worse tg at higher power). **Prefill is quant-insensitive** (~1200–1460 pp t/s, compute-bound).

## Known Issues

None found — result-only submission, no source to review.

## Open Questions For The Contributor

To raise to `B70-verified`: re-run `bench-q8q4.sh` on the reference lab's B70(s) with the maintainer's storage layout, and confirm the Q8/Q4 tg ratio (~0.5–0.6×) holds on the reference kernel/runtime.

## Disposition

Stays `community/` as `B70-tested` (contributor hardware). Promote toward `results/` only after a reference-lab re-run. Directly complements the FP8 thread in PR #9.
