# TP1 vLLM works on the XPU nightly image; XPU graph is a record-candidate lever; MTP at TP1 is verify-step-bound; graph+MTP corrupts outputs

Date: 2026-08-22/23. Follow-up to
[the pinned-image TP1 blocker](2026-08-22-qwen38-tp1-vllm-bringup-finding.md).
Data: [`2026-08-22-qwen38-tp1-vllm-nightly-matrix.json`](../data/2026-08-22-qwen38-tp1-vllm-nightly-matrix.json).
Raw runs: `bench-results/.../tp1-nightly-20260822/`. Driver:
[`run-20260822-qwen38-tp1-nightly-docker-bench.sh`](../scripts/run-20260822-qwen38-tp1-nightly-docker-bench.sh).

## Setup

- Image: `vllm/vllm-openai-xpu:nightly-e9d1398d9edfd90fcc1cf783805240e3effec013`
  (main-branch nightly 2026-08-22, reports `vllm 0.26.1rc1.dev1102+ge9d1398d9`,
  torch 2.13.0+xpu; digest `bc979d1ba312…`). Its commit is dated 11
  calendar days after v0.27.1, but the release tag is not its ancestor; treat
  the two as non-descendant comparators rather than a linear newer/older pair.
- Model: our quality-default AutoRound INT4 W4A16 (`quantization=inc`), single
  B70 (GPU0), TP1, 32K maxlen, `--max-num-seqs 1`, chunked prefill 1024,
  prefix caching OFF (cache-zero policy), f16 dtype.
- **Container bring-up fix** (the nightly's first boot died in oneCCL before
  any vLLM code ran): `CCL_ZE_IPC_EXCHANGE=sockets` + bind-mount
  `/dev/dri/by-path:ro` + `--ipc=host`. Root cause: pidfd exchange is
  unsupported in the container, and the drmfd fallback needs to opendir
  `/dev/dri/by-path`, which `--device /dev/dri` alone does not provide. Even
  TP1 hits this via a world-size-1 warmup all_reduce in
  `xpu_worker.init_device`.
- Metric: conventional decode (median over 25 fixed realistic prompts of
  tokens 1–100 rate after TTFT), cache-zero gated by the harness. This is a
  diagnostic benchmark (not a sealed record run).

## Headline results (conventional decode, single B70)

| Config | decode tok/s | TTFT s | prefill tok/s | acceptance | output vs oracle |
| --- | ---: | ---: | ---: | ---: | --- |
| MTP off, f16 KV (boot A / B) | **23.72 / 24.25** | 0.275 | 281 | — | oracle pair |
| MTP off, f16 KV, **XPU graph ON** (boot A / B) | **30.22 / 30.26** | 0.278 | 278 | — | 23/25, 20/25 (faithful) |
| MTP off, fp8_e4m3 KV | 24.10 | 0.274 | 281 | — | **3/25 (divergent)** |
| MTP1, f16 | 4.51 | 0.488 | 168 | 1.91 / 2 | 23/25 (faithful) |
| MTP2, f16 | 4.41 | 0.412 | 199 | 2.70 / 3 | 23/25 (faithful) |
| MTP3, f16 | 4.30 | 0.519 | 161 | 3.47 / 4 | 24/25 (faithful) |
| MTP1, f16, XPU graph ON | 7.63 | 0.287 | 269 | **1.00 (0 %)** | **0/25 (CORRUPT)** |
| any MTP, fp8_e5m2 KV | fail | — | — | — | `NotImplementedError` |

1. **TP1 vLLM is unblocked.** The pinned `0.20.2rc1` TP1 crashes
   (`_zero_kv_blocks_kernel` / eager init) do not exist on the nightly.
2. **XPU graph (`VLLM_XPU_ENABLE_XPU_GRAPH=1`, default OFF on the nightly) is
   worth +25 % MTP-off** — 24.25 → 30.22 tok/s — and its outputs match the
   graph-off oracles within the lane's own boot-to-boot envelope. **30.22
   beats the promoted llama.cpp Q4_K_M TP1 conventional record (27.82).**
   The objective battery on the graph config passed (`pass_all`, code canary
   `14`, 8-run repeat stable, 8K needle). No `--baseline-json` was supplied,
   so its empty-comparison `baseline_match_all=true` field is not oracle
   evidence. A repeat boot measured **30.2569** (pair
   30.2178 / 30.2569, 0.13 % spread; +8.7 % over llama.cpp TP1). Cross-boot
   sha drift on the graph pair (19/25) matches the graph-off envelope, so the
   nondeterminism caveat in (6) applies to this config equally.
3. **MTP at TP1 is functional and output-faithful but verify-step-bound.**
   Acceptance is excellent at every depth (1.91/2, 2.70/3, 3.47/4) yet net
   decode collapses ~5x. Per-step time: 42 ms (off) → 424 (MTP1) → 613
   (MTP2) → 806 (MTP3) — a consistent **~190–200 ms marginal cost per extra
   verify token**, ~4–5x the cost of a whole MTP-off step. Deeper drafts
   cannot amortize a linear per-token verify penalty, so the ladder is flat
   (4.5 / 4.4 / 4.3). MTP also degrades prefill (281 → 160–200 tok/s) and
   TTFT (0.27 → 0.41–0.52 s).
4. **XPU graph + MTP is a correctness bug, not just a perf bug**: 0 % draft
   acceptance (77 drafted, 0 accepted in steady state) AND wholesale output
   corruption — 0/25 oracle match, every prompt diverges. The verify forward
   under graph capture produces wrong logits. Upstream-reportable; entered in
   DO-NOT-REPEAT.
5. **KV dtypes**: fp8_e5m2 is hard-refused by FlashAttention on this device.
   fp8_e4m3 boots and is speed-neutral at short context (24.10) but changes
   outputs on 22/25 prompts — a capacity lever only, quality-uncertified,
   consistent with the llama.cpp q8_0-KV finding that KV quantization is not
   output-preserving.
6. **Cross-boot nondeterminism**: two identical MTP-off boots agree on only
   20/25 outputs (within-boot repeat is stable — the quality battery's 8-run
   repeat passes). Engine config points at autotuned kernel selection
   (`benchmark_combo_kernel`, inductor) varying per boot. Decode medians
   wobble ~2 % between boots (23.72 vs 24.25). Consequence: **this lane
   cannot claim cross-boot token-exactness** yet; oracle comparisons above
   use match-vs-either-boot and the 20-prompt boot-stable subset.

## Why the community's MTP numbers don't transfer (hypotheses, testable)

The r/LocalLLaMA B70 report (52 tok/s MTP2 on vLLM 0.27.1) used a **GPTQ**
checkpoint → GPTQ GEMM kernels. Our AutoRound model loads via
`quantization=inc`. Prefill at m=1024 is fine (281 tok/s), so large-m GEMM is
healthy; the ~190 ms/extra-token cost lives in the small-m>1 verify shapes —
either the INC W4A16 GEMM falls off its m=1 fast path, or the 48 GDN
linear-attention layers process verify tokens serially with heavy per-token
overhead. Discriminating tests: (a) same model on the v0.27.1 image (image
regression vs model-path), (b) GPTQ checkpoint on the nightly (quant-path),
(c) kernel-level profile of one verify step. None run yet.

## Disposition

- Record path: graph-on MTP-off TP1 has an objective battery pass + 0.13 %
  speed repeat — **the single-card diagnostic conventional leader at ~30.2
  tok/s** for this model. The speed captures used `ignore_eos=true`. A sealed
  record run + LMX submission are separate, user-gated steps; the cross-boot
  token-exactness caveat must be disclosed in any submission.
- MTP at TP1 stays OFF until the verify-step cost is understood; the drafting
  itself is proven (acceptance 87–91 %/position).
- fp8_e4m3 documented as capacity-only; e5m2 documented unsupported.
- Graph+MTP quarantined (correctness).
