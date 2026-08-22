# B70/XPU optimization ideas from community sources (untried or open on lab lanes)

Date: 2026-08-21. Author: lab. Sources reviewed:
[`community/field-reports/kydo/mlxfast-qwen38-27b-mlx-challenge/`](../community/field-reports/kydo/mlxfast-qwen38-27b-mlx-challenge/README.md)
(Apple Silicon challenge, methodology + spec-decode techniques) and
[`community/field-reports/sergiiob/b70-cookbook-family-hub/`](../community/field-reports/sergiiob/b70-cookbook-family-hub/family-hub-2026-08-21.md)
(B70 vLLM-XPU cookbook hub). Focus is Intel Arc/XPU (B70); MLX items appear
only where they transfer. Each idea lists its evidence, what exists in the lab
today, the first probe, and the acceptance gate. Nothing here is a result;
every entry starts as `untested on the pinned lab stack`.

## Ranked summary

| # | Idea | Source | Expected size | Cost to first signal |
| --- | --- | --- | --- | --- |
| 1 | Adaptive per-round draft depth | MLX + cookbook acceptance tables | medium–large | one instrumented run |
| 2 | 16,384 scheduler-budget A/B | cookbook | medium | hours |
| 3 | Prefix-cache collapse at C5 diagnosis | cookbook | medium (concurrent lanes) | hours |
| 4 | Acceptance-tuned MTP head weights | MLX | large, uncertain | days+ (training) |
| 5 | Verify-block assembly / KV rollback profiling | MLX | small–medium | one profile |
| 6 | Serial-anchored median-speedup scoring + anti-gaming screen | MLX | process, not speed | docs/harness |
| 7 | DFlash for Qwen3.8-27B on B70 | cookbook (Nemotron) + MLX (DFlash 2) | large if it ports | weeks (weights) |
| 8 | MTP mixed-token path support | cookbook (gap) | unblocks mixed loads | unknown |
| 9 | rms_norm rounding parity on next stage rebuild | upstream #534 | correctness/parity | fold into rebuild |
| 10 | WSLC negative recorded | cookbook | none (avoidance) | none |

## 1. Adaptive per-round draft depth (0–8)

- **Evidence:** MLX top runs reached ~3.9 accepted tokens/round by adapting
  draft count per round instead of fixing it. Cookbook's own full-context
  table shows fixed depth is regime-wrong on B70 too: MTP4 acceptance falls to
  66.91% (p130944/g128) / 59.81% (g512) while MTP1 holds 89.22%; their
  guidance ("MTP4 short C1, MTP2 at 128K") is a manual, static version of this
  idea.
- **Lab status:** all lab lanes use fixed `num_speculative_tokens`
  (MTP1/2/4/5). Untried.
- **First probe:** log per-round accepted-token distribution on the Qwen3.8
  AutoRound-INT4 TP2 lane across short and 128K-context prompts; if the
  distribution is wide, a depth scheduler pays. Implement as bucketed depths
  (e.g. {1,2,4}) rather than continuous to protect shape specialization.
- **Gate/risk:** token identity vs serial must hold (same gate as the
  determinism-pad protocol); every bucketed depth must be precompiled and
  covered by the sealed compile cache — dynamic shapes are an identity break
  under the lab's cache tripwire.

## 2. `--max-num-batched-tokens` 16,384 A/B

- **Evidence:** cookbook measured +17.6% prefill / +12.0% decode at p4096 on
  their nightly-digest image (16,384 vs 8,192, same recipe) — a
  scheduler/memory-layout effect, not chunk count.
- **Lab status:** untested on the lab's pinned build (different image/stack).
- **First probe:** p4096 A/B on the Qwen3.8 INT4 lane at 8,192 vs 16,384;
  record head-of-line behavior with a short request adjacent to a long
  prefill, and watch VRAM headroom.
- **Gate:** median client post-first tok/s and p4096 input rate; identity
  unchanged (cache manifest, binary identity). Author-stated caveats
  (head-of-line, activation spikes) must be re-observed, not assumed.

## 3. Prefix-cache collapse at concurrency (C5)

- **Evidence:** cookbook reports 0–38% prefix-cache hits at C5 vs 91% at C1 on
  their mixed-split v5 + draft-INT4 build; warm-session TTFT at Cn is their
  flagged open issue.
- **Lab status:** lab concurrency lanes have not characterized this.
- **First probe:** cache-hit tracing at C1/C5 on the lab build with the
  concurrent mixed-split config; classify miss cause (eviction, namespace,
  chunk-size mismatch, draft-INT4 interaction).
- **Gate:** hit-rate distribution per concurrency level; no identity changes.

## 4. Acceptance-tuned MTP head weights

- **Evidence:** MLX made the MTP head weights editable and credits custom
  heads (trained/edited for acceptance under the exact verify constraints)
  with the largest acceptance gain (~1–2 → ~3.9 tokens/round combined with
  adaptive depth).
- **Lab status:** lab quantizes/preserves heads (draft-INT4) and has the
  source-only TP-local top-K rerank candidate
  (`experiments/qwen38-27b-b70/notes/2026-08-18-autoround-int4-draft-topk-rerank-candidate.md`),
  but has never optimized acceptance itself. Upstream prior art landed this
  week: vllm `d6247d717` replicates the DSpark Markov head across TP ranks.
- **First probe:** acceptance-edit or distill the Qwen3.8 MTP head against the
  lab's deterministic verifier on a fixed prompt set; measure acceptance delta
  per depth before any serving test.
- **Gate:** exact token identity vs serial on the lab's frozen suites; quality
  oracle pass; determinism suite (the pad-era six-arm protocol applies).

## 5. Verify-block assembly / KV rollback latency

- **Evidence:** MLX solvers found compounding wins in verify-pass assembly and
  KV snapshot/rollback once drafting ~4 tokens/round.
- **Lab status:** the lab's vLLM-XPU spec path has margin/draft-quant work but
  no published profile of verify-block assembly or rollback copies.
- **First probe:** profile the verify step at MTP5/TP2 (assembly, KV
  snapshot/rollback, scheduler bookkeeping); only then decide where to cut.
- **Gate:** per-step verify latency; token identity unchanged.

## 6. Serial-anchored scoring + anti-gaming screen (process adoption)

- **Evidence:** mlx.fast scoring = median of eight prompt speedups over pure
  serial decode (anchor 1.0, floor 0.90, ceiling 3.0) with automated
  anti-gaming screening and a contribution-ranked leaderboard.
- **Lab status:** the lab already enforces the identity half of this (the
  2026-08-20 margin audit invalidated two margin-assisted records; the pad
  prereg requires PAD0 ≥2 variants / PAD1 mutual identity). Not yet adopted:
  the serial-anchored median-speedup publication format.
- **Action:** publish B70 speed claims as median-of-N serial-anchored speedups
  alongside tok/s, and keep the margin/identity screens as the standing
  anti-gaming gate for any leaderboard-bound number.
- **Gate:** documentation change; no measurement risk.

## 7. DFlash for Qwen3.8-27B (watching brief)

- **Evidence:** Nemotron-3.5-Lightning hits 186.61 C1 on B70 vLLM XPU via
  DFlash n=7, proving the DFlash runtime path on this hardware; mlx.fast is
  evaluating DFlash 2. The lab has DFlash experiment history
  (`experiments/deepseek-v4-flash-reap-xpu-b70/`).
- **Lab status:** no Qwen3.8 DFlash head exists; porting needs trained DFlash
  weights for this model — a research task, not a config change.
- **Action:** tracking only; revisit if a Qwen3.8 DFlash checkpoint appears or
  DFlash 2 publishes a training recipe.

## 8. MTP mixed-token path (gap, tracker)

- **Evidence:** cookbook guidance is "no-spec for mixed long-prefill +
  short-chat loads" because the MTP mixed-token XPU path is unsupported.
- **Lab status:** confirmed-absent feature, not a lab failure.
- **Action:** keep a tracker entry; any lab work here is kernel/scheduler
  feature work, so it competes with the in-flight determinism-pad rollout for
  the same trees. Do not start before the pad lands.

## 9. rms_norm rounding parity (fold into next rebuild)

- **Evidence:** upstream vllm-xpu-kernels `4543b58` (#534, 2026-08-21) aligns
  rms_norm rounding with CUDA to avoid precision loss; `95d80c7` bumps
  sycl-tla (kernel-generation dependency).
- **Lab status:** pins held at `2dd55f38`; not adopted.
- **Action:** when a stage rebuild next happens for other reasons, review #534
  for cross-stack parity impact and expect binary-identity churn from the
  sycl-tla bump (manifests must be regenerated, caches re-sealed).
- **Gate:** the standard identity matrix (model manifest, binaries, cache
  manifests, oneCCL) before/after.

## 10. Windows WSLC negative (recorded)

- **Evidence:** cookbook's WSLC kit is 2.4–2.8× slower than its Docker Desktop
  kit (~70 tok/s class) on the same single-B70 Windows 11 host.
- **Action:** none beyond this record — Windows deployment questions go to the
  Docker Desktop kit; do not re-test WSLC without a stated new hypothesis.

## Explicit non-goals from these sources

- MLX/Metal kernel edits (SDPA, MoE gather-GEMM, RoPE) — platform-specific,
  already covered in kind by the lab's own XPU kernel program; nothing to port.
- The MLX headline numbers (87.9 tok/s on M5 Max) — different hardware,
  metric, and checkpoint class; orientation only.
- The CUDA challenge track Kydo announced — off-hardware for this lab.
