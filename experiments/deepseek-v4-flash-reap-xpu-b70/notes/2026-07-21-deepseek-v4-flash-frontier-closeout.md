# DeepSeek V4 Flash on 4x B70 — Frontier Closeout & Lessons

Date: **2026-07-21** · Status: **lane paused at a fully-characterized frontier; record intact; all assets preserved**

This consolidates a multi-day push to move DeepSeek V4 Flash REAP K160 past its
80.82 tok/s target-verified record on four Intel Arc Pro B70s. Every lever is
now characterized with evidence. The record is unchanged and LocalMaxxing-approved.

Promoted publication: [closed result packet](../../../results/deepseek-v4-flash-k160-b70/README.md),
[standalone fail-closed repro](../../../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md),
and [exact source archive](../../../patches/deepseek-v4-flash-reap-xpu-b70/README.md).

## Records (unchanged)
- **Target-verified speculative record: 80.820052 tok/s** (M=7 DSpark draft / M=8 exact verify), LocalMaxxing `cmrquta9905w3lg013m5vxoqx`.
- Nonspeculative direct-MoE record: ~43.77 tok/s.

## Corrected roofline (a real result of this push)
- True achievable B70 memory bandwidth is **579 GB/s/card** (best 603.8, within 0.7% of the 608 spec) — the earlier 527 GB/s was a *microbench-kernel* limit, not a memory limit. ECC is already disabled (full 32 GB exposed); no thermal/power throttling (175-183 W of 230 W TDP, 2800 MHz, "Not Throttled").
- **Nonspeculative bandwidth roofline = 151 tok/s** (was computed 137). **160 nonspec is physically impossible** — it needs 613 GB/s/card, above the 608 spec, at 15.3 GB/token (the model's mixed-precision serving; uniform-Q4 would be ~8 GB/token → higher ceiling but a different, lower-fidelity model).
- Evidence: `notes/2026-07-20-b70-bandwidth-recovery-investigation.md`.

## The core finding: M=1 decode is occupancy-starved, and only speculation fixes it
At M=1, decode fires ~200 tiny kernels/token, most **launch/latency-bound** — the MXFP4 GEMV runs at 288 GB/s (EU 40% idle), shared-down FP8 at 150 GB/s (EU 83% idle). A single token simply doesn't have enough independent work to fill the EUs. Neither precision, layout, nor workgroup-splitting manufactures parallelism that isn't there. **The only thing that fills the starved EUs is more work per launch — which is exactly what speculation's M=8 batching does.** This is why the spec record (80.82) is ~2× the nonspec record (43.77).

## Closed lanes (all with evidence — do not re-run without a new mechanism)
1. **Config/versions**: VTune/unitrace confirmed already optimal — async scheduling on, `FULL_AND_PIECEWISE` graph (NOT eager), custom fused kernels, versions pinned. `notes/2026-07-20-nospec-unitrace-attribution-crosscheck.md`.
2. **Exact kernel tuning**: 3 iterations recovered ~0.1 ms/token total (GRF128 regressed; prefetch +0.026; oneDNN retunes regressed/inexact). `notes/2026-07-20-nospec-m1-kernel-efficiency-iteration{1,2,3-mhc}.md`.
3. **Fixed-geometry decoder (Option 4)**: substrate **proven feasible** — a raw Level-Zero command list records mixed Triton+oneDNN into ONE boundary, bitwise-exact, 0 host syncs (Phase 0/0b). `M1AttentionBoundaryV1` collapses 14 submissions→1, bitwise-exact on 43 layers, nests in PIECEWISE with no eager break. **But the endpoint is −0.18 ms/token**: submission-collapse doesn't recover *device-kernel execution* time (that's the 9.4 ms), only host-submission overhead (already graph-amortized). This is the 5th independent confirmation (native-K2 +0.9, persistent-K-step ~0, M2 chain +0.11, M1-attention −0.18) that submission collapse caps at ≤0.9 ms. `notes/2026-07-20-option4-phase1-m1-attention-debug-to-done.md` and the option4-decoder/ substrate.
4. **Occupancy exploits**: MXFP4 tile-major prepack *fragmented coalescing* (−1.3 ms) and dense FP8 more-workgroups *lowered* occupancy (~0 ms). The M=1 occupancy limit is not kernel-tunable. `notes/2026-07-21-dense-fp8-split-n-occupancy-rejection.md`, `notes/2026-07-20-mxfp4-tile-major-prepack-rejection.md`.
5. **Inexact fusion**: fast MHC fusion changes ~50% of greedy tokens — MHC arithmetic is load-bearing to quality. `notes/2026-07-20-nospec-m1-kernel-efficiency-iteration3-mhc.md`.

## Speculation lane (the only lever with headroom — and it's data-gated)
- **Hybrid draft designed + validated**: Markov owns P1-P3 (78/77/71% conditional), EAGLE owns P4-P7 (73-74% trained), crossover k=4, handoff **bit-exact**. Offline splice: **3.606 emitted/cycle vs Markov 3.507 (+2.8%)** on the current head; EAGLE-alone is worse (2.375) because its P1 is weak. `notes/2026-07-21-markov-eagle-hybrid-draft-design.md`, `notes/2026-07-21-hybrid-splice-offline-experiment.md`.
- **EAGLE head is DATA-LIMITED**: a one-layer 2048-wide EAGLE-3 head trained on the **1M-token** captured corpus plateaus at **~67-68% mean P2-P7** across three LRs (2e-4 destroyed the warm-start; 2e-5 flat; 5e-5 unstable-flat). Loss keeps dropping while DEV acceptance doesn't — overfitting, not under-tuning. Best head preserved (~68% P2-7). Reaching ~78-80% (→ hybrid ~90 tok/s) needs the design's **10-20M-token** corpus. `notes/2026-07-21-k160-eagle-*.md`.
- **Why the current hybrid isn't worth integrating**: +2.8% acceptance is too thin to survive the extra draft-compute of running Markov + a 7-step EAGLE rollout per cycle (~3-8% cycle growth) — it would likely lose at the endpoint. It becomes worth it only at ~+11% (trained head).

## Honest ceiling
**80.82 is at or very near the true frontier for this exact model on these four B70s.** The only remaining real gain is the ~90 tok/s hybrid, gated on a 10-20M-token capture + multi-day training. **160/230 is not reachable on this hardware/model** — it would need the hybrid (~90) *and* a leaner target cycle (which the decoder proved submission-collapse can't deliver) *and* deeper speculation, a combination this silicon doesn't support.

## Reusable assets (preserved, checksummed)
- **80.820 record source and launcher** — exact-history Git bundles, reviewable
  combined patches, pinned launcher, validity packet, and evidence links in the
  promoted publication above.
- **Fixed-geometry decoder substrate** `option4-decoder/` — raw Level-Zero command-list builder + parity harness (proven, bitwise-exact). Reusable for any future device-resident decode work.
- **M2/M4/M8 real-cycle corpora** + no-model 4-card replay worker (70/70).
- **EAGLE pipeline**: exact feature-capture path, 1M-token corpus + 50K DEV set (checksummed), the trainer (`train-k160-eagle-longhaul.py`), best head checkpoint (~68% P2-7), and the offline hybrid-splice analyzer.
- **Frozen held-out spec-eval harness** + packs (note: exposed to a few agents' broad searches — regenerate fresh before any final promotion).
- **Bandwidth microbench** achieving 579 GB/s (correct random-fill, avoids the compression artifact).
- Detailed per-experiment notes under `notes/` (dated); orchestrator resume at `ORCHESTRATOR_HANDOFF.md`.

## Reopen conditions
Resume this lane only for: (a) a 10-20M-token EAGLE re-capture + training run aiming at ~90 tok/s via the validated hybrid; or (b) a genuinely new device-kernel mechanism that reduces *device execution* time (not submissions) — e.g. a fused multi-kernel that does more work per launch. Everything else is a preserved closure.
