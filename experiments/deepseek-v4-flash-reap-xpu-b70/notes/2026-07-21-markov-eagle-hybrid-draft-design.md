# Markov + EAGLE hybrid draft design — 2026-07-21

Status: **design + analysis only**. No model load, no GPU work, no source
change, no held-out reveal. This note specifies a per-position hybrid draft that
keeps the exact M=8 K160 verifier unchanged and only changes which token IDs
fill the seven draft slots.

## Numbers first

- Baseline (Markov DSpark7), combined DEV: **35.815% draft acceptance, 3.507
  emitted tok/cycle**, 781 cycles. Record/public-continuity population: **~3.117
  emitted/cycle at 80.82 tok/s** (cycle ≈ 38.6 ms).
- Markov is best at P1-P3; the current EAGLE checkpoint is best at P4-P7. Per
  position, **conditional** acceptance (given all earlier positions survived):

  | Pos | Markov cond. | EAGLE cond. (current ckpt) | Hybrid picks | Hybrid cond. |
  |---:|---:|---:|:--|---:|
  | 1 | **78.23%** | 56.90% | Markov | 78.23% |
  | 2 | **76.92%** | 52.74% | Markov | 76.92% |
  | 3 | **71.49%** | 59.33% | Markov | 71.49% |
  | 4 | 66.37% | **68.85%** | EAGLE  | 68.85% |
  | 5 | 66.82% | **72.93%** | EAGLE  | 72.93% |
  | 6 | 69.13% | **74.23%** | EAGLE  | 74.23% |
  | 7 | 64.08% | **73.69%** | EAGLE  | 73.69% |

  Markov numbers: dspark7 diagnostic (combined DEV, 781 cycles). EAGLE numbers:
  single-card signal run, complete-DEV recursive rollout, best (final)
  checkpoint at 59.9995% of one epoch.
- Crossover is at **P4**. Source scheme = **Markov for P1-P3, EAGLE for P4-P7**
  (default crossover k=4; k is a tuned scalar, not a fixed law).
- Hybrid emitted/cycle (per-position max, combined DEV): **~3.61** with today's
  under-trained EAGLE; **~3.70** if EAGLE deep conditionals reach 0.75; **~3.89**
  if they reach the 0.82 design midpoint. Scaled to the record population:
  **~3.25–3.55 emitted/cycle → ~84–92 tok/s at unchanged cycle cost.**
- Milestone acceptance at today's 38.6 ms cycle: **100 tok/s = 3.86 emitted/cycle;
  130 tok/s = 5.02; 160 tok/s = 6.18** (≈74% mean marginal acceptance across 7
  drafts). Hybrid alone reaches the high-80s/low-90s, not 100; 130/160 also need
  a leaner target cycle.

## 1. Architecture

### 1.1 Where the selector lives

The live XPU integration seam is the DSpark speculator, not the design-time
`xpu/dspark.py` (that file is now only a compiled artifact; its role is a
reference). Concretely:

- `vllm/v1/worker/gpu/spec_decode/dspark/speculator.py`
  - `_generate_draft(...)`: runs the parallel backbone (`_run_model`) then
    `_sample_sequential(...)`.
  - `_sample_sequential(...)`: the `for i in range(n_spec)` loop that fills
    `self.draft_tokens[:, i]` left-to-right with the Markov head, carrying
    `prev` (the previously sampled token) as the intra-block dependency.
- `.../dflash/speculator.py :: propose()`: fuses `aux_hidden_states` via
  `combine_hidden_states` (main_proj), stores them in `self.hidden_states`, and
  calls `precompute_and_store_context_kv`. This is where the EAGLE anchor
  features enter.
- `.../autoregressive/speculator.py`: the true recursive per-position rollout
  the EAGLE head needs (Eagle extends `AutoRegressiveSpeculator`).

The hybrid is a new speculator (`HybridMarkovEagleSpeculator`) that owns both
drafters and, at each of the 7 positions, writes into the single existing
`self.draft_tokens[:, i]` buffer from the selected source. The Markov backbone +
`_sample_sequential` are reused verbatim; the EAGLE head is the recursive head
from the EAGLE design note (`[4,22,43]` taps, width-2048, one dense layer).

### 1.2 The handoff (the hard part)

Question: can the EAGLE head start at position 2 given Markov's P1 token, or
does it need its own position-1 pass?

Answer: **EAGLE must run its own position-1 (and P2, P3) forward to build its
latent/KV state, but its P1-P3 token outputs are discarded.** It cannot skip the
forward passes — the recurrence at P4 requires the KV/latent accumulated from the
anchor features `z0 = fuse(f4(t), f22(t), f43(t))` and the intervening token
embeddings. It can skip the P1-P3 *token head / argmax* (no LM-head projection
needed there), which saves compute.

The state flow within one cycle ending at committed target position `t`:

1. Both drafters anchor on the **same committed prefix**: the current token at
   `t` and (for EAGLE) the target aux features `f4(t), f22(t), f43(t)` returned
   by the previous target forward. No future/verified feature is used — none
   exists yet.
2. Markov proposes `d1, d2, d3` (its strong positions), carrying `prev` as
   today.
3. EAGLE runs recursively but is **teacher-forced on the Markov prefix**: at
   step i≤3 its recurrence input is the embedding of Markov's `d_i` (not
   EAGLE's own argmax), advancing EAGLE's latent/KV. This is exactly the
   distribution EAGLE was trained on (teacher-forced on the greedy prefix), as
   long as the Markov tokens are the ones that will be accepted.
4. At P4-P7, EAGLE emits its own argmax tokens `d4..d7`, each conditioned on the
   full Markov+EAGLE prefix via its recurrence.
5. The 7 IDs `[d1(M), d2(M), d3(M), d4(E), d5(E), d6(E), d7(E)]` become the seven
   speculative rows. Nothing is accepted or emitted in the drafter.

Correctness of the handoff rests on one fact: if any Markov token `d_i (i≤3)` is
wrong, the M=8 verifier truncates the cycle at position i, so the EAGLE tokens
downstream are never emitted and their mis-conditioning is harmless. When the
Markov prefix is correct (the only case where EAGLE tokens can be emitted),
EAGLE saw exactly the greedy prefix it was trained on. So the hybrid is, by
construction, **≥ max(Markov, EAGLE) per position** and its emitted/cycle is
≥ the Markov baseline of 3.507 for any EAGLE quality.

### 1.3 Draft state / feature flow between cycles

- The EAGLE anchor features are the target's aux hidden states at post-layer
  boundaries `[4,22,43]` (zero-based target layers `[3,21,42]`), captured in the
  same target forward that commits token `t`. The record path currently taps
  `[40,41,42]` for DSpark; the target must additionally expose the `[4,22,43]`
  taps (a `model.py` capture change; see Risks). The reduction is the existing
  `mean_stream(hc_post(...))`, BF16[4096], same at train and infer.
- Draft KV is cycle-local scratch: build from the committed prefix, discard all
  7-step scratch after verification (both Markov context-KV and EAGLE recurrence
  KV). The verifier's committed token (rejection token or all-accept bonus)
  enters the next target call, whose fresh aux features anchor the next cycle.
- Markov keeps its persistent rank-256 head exactly as today; EAGLE keeps only
  weights (no cross-cycle state). No partial draft-cache rollback.

## 2. Exactness

The hybrid changes **only proposals**. The transaction downstream of proposal
production is untouched:

```
target aux features + committed token
        |
  Markov (P1-P3)  +  EAGLE recursive (P4-P7, teacher-forced on Markov prefix)
        |  -> draft_ids[1,7]
existing fixed-M7 target-input builder
        |
unchanged K160 forward on [current + 7 drafts], width M=8
        |
existing target-owned greedy prefix compare / rejection / bonus / commit
```

Invariants (unchanged): target input width = 8; consecutive positions; K160
computes all 8 rows; accepted length derived only from target outputs; rejection
emits the target token at first mismatch; all-accept emits the exact target
bonus; **no draft-only acceptance**. Draft confidence / crossover index are
policy inputs only.

Gates it must pass (same order as the EAGLE design §5.2): proposal-interface
gate (exactly 7 deterministic target-vocab IDs, no stale rows), target-provenance
gate, **greedy-equivalence gate (spec output token IDs == same-build target-only
greedy IDs, 100%)**, state gate (rejection/bonus/EOS/reset/reorder), four-card
replay gate (positions 28 and 58 included), and the **cycle-cost gate**
(acceptance without net emitted-per-wall-cycle improvement is a rejection). No
benchmark routing; crossover policy frozen before any held-out reveal.

## 3. Expected payoff

Method: hybrid conditional = max(Markov, EAGLE) per position (§ table);
marginal_i = product of conditionals 1..i; emitted/cycle = 1 + Σ marginal_i.
Both source tables measured on DEV populations, so combine on the combined-DEV
scale, then scale to the record/public population by the measured baseline ratio
(3.117/3.507 = 0.889).

| Scenario | P4-P7 EAGLE cond. | Emitted/cycle (combined DEV) | Emitted/cycle (record pop.) | tok/s @ 38.6 ms |
|---|---:|---:|---:|---:|
| Baseline Markov | — | 3.507 | 3.117–3.20 | 80.7–80.8 |
| Hybrid, current ckpt | 0.69–0.74 | ~3.61 | ~3.25 | ~84 |
| Hybrid, EAGLE→0.75 | 0.75 | ~3.70 | ~3.34 | ~86–88 |
| Hybrid, EAGLE→0.82 (design mid) | 0.82 | ~3.89 | ~3.51 | ~90–92 |

Assumptions and caveats:

- **Constant cycle time.** These tok/s hold only if the added EAGLE rollout fits
  the ≤3.0 ms draft+policy budget. Running *both* drafters costs more than either
  alone; any cycle-time growth scales tok/s down proportionally (Risk 1).
- Cross-population transfer (combined-DEV table applied to record population)
  assumes the per-position *relative* lift is stable across suites. Public-subset
  Markov conditionals are lower (P3=64%, P7=51%) so the EAGLE crossover likely
  moves earlier (to P3) on prose-heavy public traffic, which would *raise* the
  lift — treat ~84–92 tok/s as the plausible band, ~86–88 as the point estimate.
- EAGLE numbers are from a 60%-of-one-epoch checkpoint whose deep curve was
  still rising (mean P2-P7 53.8→62.2→66.6→66.96%). More training moves the
  hybrid toward the upper rows; the lower row is a near-guaranteed floor because
  hybrid ≥ Markov by construction.
- The hybrid does **not**, on its own, reach 100 tok/s. Milestones at the current
  38.6 ms cycle: **100 → 3.86 emitted/cycle; 130 → 5.02; 160 → 6.18** (~74% mean
  marginal, i.e. ~96% conditional at every deep position given P1≈82%). 100
  needs a fully-trained EAGLE deep block *and* some P2-P3 lift or a modestly
  cheaper cycle; 130/160 need the leaner target cycle (MoE M7/M8 activation
  portfolio, DPAS W2) compounded on top — deeper speculation cannot get there at
  today's cycle cost.

Category note: Markov is strong on code/copy/low-locality (local transitions);
EAGLE is expected to help most on **prose** (382/781 DEV cycles, weakest at 3.010
emitted/cycle), where deep local transitions are unpredictable but target
features carry structure. The crossover k should be allowed to differ by nothing
except position (no category routing — that violates the anti-cheating rule); a
single global k tuned on DEV is the compliant lever.

## 4. Risks

1. **Draft-compute cost erodes/cancels the gain (biggest risk).** The hybrid
   runs the Markov backbone *plus* a 7-step autoregressive EAGLE rollout every
   cycle. Even skipping EAGLE's P1-P3 token heads, 4 deep LM-head projections on
   the shared full-vocab head (~0.45 ms/rank each ≈ 1.8 ms) plus 7 recurrence
   steps can push draft+policy over the 3.0 ms budget. The measured lift is only
   +0.1 to +0.4 emitted/cycle; if the cycle grows by >~4% the net tok/s is flat
   or negative. This is exactly the "isolated acceptance win that lost at
   endpoint" failure class in ORCHESTRATOR_HANDOFF §10. **Net tok/s, not
   acceptance, decides.** Mitigation: skip EAGLE token heads on Markov-owned
   positions; reduced-vocab EAGLE head; later, fuse into the fixed-address
   transaction.
2. **Feature availability / capture latency.** EAGLE needs `[4,22,43]` aux
   features of the committed prefix; the record path taps only `[40,41,42]`.
   Exposing the extra low/mid taps adds per-cycle capture + `combine_hidden_states`
   cost and a `model.py` change. The taps must be tagged and verified (`[4,22,43]`,
   layers `[3,21,42]`) — the loader must fail closed on an untagged/ambiguous
   tuple, and must not confuse post-layer boundary IDs with DSpark zero-based
   layer IDs.
3. **Position-1 handoff correctness.** EAGLE must advance its latent/KV on the
   Markov tokens, not its own argmax, for P1-P3. A bug that feeds EAGLE its own
   P1-P3 tokens silently mis-conditions P4-P7 and quietly lowers acceptance
   without breaking exactness (still target-verified) — so it will only show as a
   soft regression. Guard with the offline teacher-forcing test (§5) before
   integration.
4. **Under-trained EAGLE gives a thin margin.** At the current checkpoint the
   P4-P7 edge over Markov is only ~2–10 conditional points on low-survival
   positions (marginal ~0.12–0.30), so combined-DEV lift is ~+0.1/cycle — likely
   below the cycle-cost break-even. The hybrid may need EAGLE trained past its
   signal gate before it clears net-positive.
5. **Category dependence.** Markov strong on code/copy; EAGLE expected stronger
   on prose. A single global crossover k is a compromise; per-category routing is
   forbidden by the contract, so the win on prose must survive being averaged
   with code where Markov already owns deeper positions.
6. **Mean-pooled MHC features** may discard four-stream state EAGLE needs
   (inherited EAGLE risk); and EAGLE-3 offline acceptance may not translate to
   endpoint — reject on net tok/s.

## 5. Smallest first experiment (offline, no reveal)

One offline pass, no model load, no serving, no held-out packs, reusing the
captured DEV traces (`data/dspark7-draft-acceptance-dev-suite-v1.json` +
complete-DEV capture) and the **current** EAGLE checkpoint
(`head-best-mean-p2-p7.pt`, sha `ef74bdbf…`):

1. For each DEV cycle, take the committed prefix and the Markov per-position
   proposals already captured.
2. Run the EAGLE head recursively but **teacher-force it on the Markov P1-P3
   tokens** (feed Markov `d1,d2,d3` embeddings as the recurrence inputs, discard
   EAGLE's own P1-P3 argmax), then read EAGLE's P4-P7 argmax.
3. Score the hybrid stream `[d1(M),d2(M),d3(M),d4(E),d5(E),d6(E),d7(E)]` against
   the greedy target continuation with the standard per-position evaluator:
   report P1-P7 conditional/marginal, overall acceptance, and emitted/cycle.
4. Sweep crossover k ∈ {2,3,4,5} to find the offline-optimal boundary.

Decision: continue only if hybrid emitted/cycle clears **~3.6 combined-DEV**
(Markov floor + a real, measurable deep lift) and P1-P3 is bit-identical to the
Markov baseline (proving the handoff). This single pass validates the handoff
correctness (Risk 3), the payoff (§3), and the crossover choice at once. Failure
is cheap and kills the hybrid before any capture-path or endpoint work. It does
**not** measure cycle cost (Risk 1) — that is the next gate and requires the
isolated fixed-M7 head timing, not this offline test.
