# mlx.fast Qwen3.8-27B challenge — reported results and design (2026-08-21)

Evidence level: `community-reported`. All numbers below are the challenge
operator's verifier-reported figures on Apple Silicon (M5 Max); nothing was
reproduced on B70 hardware. Maintainer notes are marked and narrowly scoped.

## Reported headline

- Median decode: **26 → 87.9 tok/s** (33 → 93.1 tok/s across the eight scoring
  prompts) in 7 days; prefill ~971.8 tok/s. Verifier: M5 Max.
- 31 solvers, 67 accepted improvements.
- Top runs draft and accept **~3.9 tokens/round** while matching serial output
  exactly (every emitted token must equal serial decode).
- Results upstreamed into Darkbloom; ~2× faster decode in their production
  Qwen traffic.

## Challenge design (the transferable part)

- Native MTP speculative decoding editable from day one; editable surface
  includes **the MTP head weights themselves**, the full draft/verify loop,
  and a large set of Metal kernels.
- Scoring: **median of eight independent prompt speedups over pure serial
  decode**, anchored at 1.0, floor 0.90, ceiling 3.0 — no single fixture can
  dominate.
- Leaderboard ranks **total contribution**, not just the current record.
- **Automated anti-gaming screening** before any submission scores.

## Reported winning techniques

1. Custom MTP heads trained/edited for higher acceptance under the exact
   verify constraints, combined with **adaptive per-round draft counts (0–8)** —
   credited with moving average accepted tokens from ~1–2 to ~3.9.
2. Tighter verify-block assembly and KV snapshot/rollback paths (Swift session
   code); small latency wins compound at ~4 drafted tokens/round.
3. Metal kernel edits on SDPA, MoE gather-GEMM, RoPE, RMSNorm, and small
   element-wise ops; most gains only appear at high verify width.
4. Fidelity-preserving residual/acceptance handling so higher draft depth does
   not degrade the token match rate.

## Reported next steps

Keep the MLX track live; switch to the Qwen3.8 MoE (rumored 35B-A3B);
evaluate DFlash 2 support; ship a **CUDA version of the challenge next week**;
seeking a Qwen partnership/bounty match.

## Maintainer notes

- The exact-serial-match gate plus anti-gaming screening is the same class of
  defense as this lab's 2026-08-20 margin audit (margin-assisted determinism
  claims masked runtime nondeterminism and invalidated two published records).
  Their scoring rule (median-of-N serial-anchored speedups) is directly
  adoptable for B70 submissions.
- Acceptance tuning of MTP head weights and adaptive draft depth are untried
  on this lab's B70 lanes; see the ideas doc linked from the collection
  README.
- Their verifier timing basis (median across fixed prompts, serial anchor) is
  methodologically compatible with this lab's client post-first median
  conventions; the hardware numbers themselves do not transfer.
