# Qwen3.5-4B W4A16 on B70 — lane handoff

Last updated **2026-09-09**, during the overnight identity campaign. Chains 2-6
were still running when this was written; the "In flight" section says what is
outstanding.

## What this lane is

`RedHatAI/Qwen3.5-4B-quantized.w4a16` rev `7a613872`, served through vLLM XPU's
`compressed-tensors` path onto the lab's row-invariant `XPUwNa16LinearKernel`,
with the publisher MTP head as a draft and a draft-only INT4 `lm_head` copy.
Image R276 `sha256:521eb277`. Model at `/home/steve/llm-models/qwen35-4b-w4a16`.

Packaged as `packages/qwen35-4b-w4a16-b70`, family `qwen-4b`, one card, depth 3,
**177.4 tok/s** on the strict suite with G1/G2/G3 all 12/12.

## Settled before this campaign (2026-09-07/08)

- Depth 3 is the operating point. Depths 3, 4, 5 and 6 are all lossless on the
  strict suite; 3 and 4 are tied at the top, 5 and 6 are slower.
- The FP8 build of the same model is **not** repeat-exact and is not packaged:
  three fresh-server campaigns scored 11/12, 9/12 and 11/12, with exactly three
  tie-prone prompts, each showing exactly two variants.
- TP1 long context 2K-32K, depth 3, oracle-exact throughout.

## Settled by this campaign

**Serving policy — the one operational result.** `c16` is the speculation
ceiling. Below it depth 3 is worth 35% at c8 and the gates pass. From c20 up it
costs 14-28% of throughput *and* multiplies divergence ninefold, and nothing
above reverses it: at c128, no-speculation runs 1811 tok/s against depth 3's
1167. **Size the server: 16 or fewer concurrent users, run depth 3; more than
that, run without speculation and get both.**

**TP2 is measured and lossless, on three axes.**

| | TP1 | TP2 | ratio |
| --- | ---: | ---: | ---: |
| strict suite, depth 3 | 177.4 | **240.9** | 1.36x |
| strict suite, MTP0 | 102.6 | 138.1 | 1.35x |
| 32K context, depth 3 | 149.9 | **222.0** | 1.48x |
| 32K context, MTP0 | 84.4 | 114.7 | 1.36x |

Eight strict servers across two campaigns, every comparison 12/12; 18 of 18
long-context cases byte-identical to their MTP0 oracle. The published pair's
`227.533` was an outlier — three of four passes fall in a 0.24% band and the
fourth sits 5.44% below, against a lane that normally reproduces to a quarter of
a percent. `families/qwen-4b.json` still lists `tp: [1]`; the evidence to extend
it exists and packaging was out of scope.

**No-speculation is near-exact to 128 users.** 4 divergent requests in 1728, and
c96 was perfectly exact at 576/576. Row invariance holds far past where it had
been measured.

**Divergence is a fork between two whole continuations, not corruption.** Sites
are stable across days, reboots and compilation modes — all 14 from 2026-09-07
reappeared — and the token pairs decode as synonyms (`" HTTP"`/`" Redis"`,
`" Column"`/`" Index"`). For a single-site prompt, four execution conditions map
onto exactly two continuations as a clean 2x2, byte-for-byte. Adding a second
card flips which side the sequential oracle takes.

An earlier version of this section said "no kernel change can give this model one
determined output at these positions". That is too strong, and the 9B lane has
the counterexample: a batch of **constant composition is deterministic** — 64
identical prompts in lockstep gave 64 identical outputs at 64 rows, on two cards,
eager and under graph capture. The accurate statement is that **no
row-count-invariance fix removes it under varying composition**, because several
ops in the body carry the dependence and fixing one leaves the rest; five powered
arms have now found exactly that, tonight's determinism pad being the fifth. So
**"lossless" here means the strict gates pass**, not that a server under real,
drifting load has a single determined output at these positions.

**Speculation's 18x penalty is two effects.** Six intrinsic sites amplify 9.69x;
thirteen more appear only under speculation and carry 63% of its events, where
uniform amplification predicts 22 MTP0 events and zero were seen (p 2.6e-10). A
tie-breaking intervention can only address the smaller part.

## Method findings that apply beyond this lane

1. **`max_concurrency_captured = max_cudagraph_capture_size / (1 + depth)`.**
   Source-verified and confirmed prospectively. Every depth-3 ladder rung above
   c16 in this lab has run without cudagraph replay.
   See `notes/2026-09-09-speculation-shrinks-the-captured-concurrency-range.md`.
2. **The divergence rate partly measures where the oracle landed.** When the
   sequential oracle draws a site's minority branch, the whole majority counts as
   divergent. Use the oracle-free `min%` from `summarize-arm.py`. The 9B powered
   comparisons were checked and survive.
   See `notes/2026-09-09-the-divergence-rate-partly-measures-the-oracle.md`.
3. **A ladder's exactness is a property of its prompt suite**, and which prompts
   are fragile is model-specific: `cache` is the 4B's worst at 55.6% and the 9B's
   quietest at 0.62%. A fragile suite must be rebuilt per model.
4. **Ladder pass 1 is warmup-contaminated** at low concurrency. Use pass 2 on.
5. **Verbatim ladders always report cross-base collisions** and are always
   classified `measured-output-variant`. Read `oracle_exact_count`, not
   `classification`.
6. Never quote a rung as "exact" from two passes: the `f1` arm needed 20 passes
   to see 2 events in 640 at c32.

## Tools added

In `experiments/qwen35-9b-b70/scripts/` (shared with that lane):
`analyze-divergence-positions.py` (extended with difflib alignment classes),
`analyze-site-fragility.py`, `build-fragile-suite.py`.
In this lane's `scripts/`: `summarize-arm.py` (per-rung identity, throughput,
sites, and the oracle-free `min%`), `probe-tie-margin.py`.

## In flight

Six chained runners, each waiting on the previous one's DONE file, wrappers at
`/mnt/fast-ai/bench-results/qwen35-4b-{exhaustive,fragile,gdn,depth,margin,shallow}-20260909-wrapper.log`.
Chain 1 is complete, as are `d1` (the determinism pad, a null at an 11.7% cost)
and `g1` (the fragile-suite baseline). Outstanding:

- **g2** was queued as a slot-pinning test and is not one: `--pin-slots` sets an
  `id_slot` field that vLLM accepts under `extra="allow"` and never reads, so it
  is a same-config replicate of `g1` and gives the noise estimate for the `g1`
  against `g3` comparison. Read it that way.
- **g3** staggers arrivals by 25 ms. Under the 9B lane's account — constant
  composition is deterministic, divergence needs composition to vary — this is a
  directional test of that account, and the prediction that it should raise the
  rate is on record before the arm runs.
- **s08/s16/s32/k128** the GDN speculative group size against the capture ceiling,
  the two confounded explanations of the c16 step. Both are predicted to fail
  under the 9B account; the arms eliminate them by measurement. See
  `notes/2026-09-09-preliminary-the-gdn-group-is-probably-not-the-driver.md`.
- **e1/e2/e6, t5, t6** depth as a dose at c64, plus TP2 statistics and TP2 fragile.
- **m1** the logit margin at divergence points. The 9B lane's projection probe
  used random weights whose margins are enormous, so it could not show an argmax
  move; this reads top-k logprobs at real divergence points.
- **d1s/d2s** strict gates at depths 1 and 2, which the depth sweep never covered.
- **mb** isolates whether f4's genuinely lower divergence comes from the capture
  ceiling or from `max_num_seqs`/`max_num_batched_tokens`.
- **t8/t7** the TP2 crossover rungs and TP2 past c64, the two holes in the
  consolidated throughput matrix.

## Where the mechanism work stands, and whose it is

The mechanism line is the 9B lane's, not this one's, and its notes are ahead of
anything here: `experiments/qwen35-9b-b70/notes/` rules out the cross-card
all-reduce, the norm's variance reduction, the two together, slot position,
decode-step drift, the weight-quantised GEMM's strategy selection, the FP16
vocabulary projection and graph capture — and establishes that a
constant-composition batch is deterministic while a drifting one is not. Read
those before proposing a mechanism here. This campaign contributes measurements
on a second model, not a competing account.

## Scope

In-repository evidence only, by agreement: no package or catalog updates, no
LocalMaxxing submission. Results live in this lane's `data/` and `notes/`, plus
three lab-level notes under `notes/`.
