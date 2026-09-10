# Qwen3.5-4B W4A16 on B70 — lane handoff

Last updated **2026-09-09 evening**. The overnight identity campaign is
**complete**: nine chained runners, 31 arms, zero hardware aborts, finished 07:26.
Chain 10 (the three open questions, `x1`-`x3`) finished 19:27. **Chain 11 is
running** (`y1`-`y3`, the row-chunk hypothesis for the throughput dip, wrapper
`/mnt/fast-ai/bench-results/qwen35-4b-rowchunk-20260909-wrapper.log`), with the
corrected 9B offline drift probe queued behind it.

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

**Staggered admission is bit-exact, and is the first intervention that has moved
this number.** With `--launch-stagger-ms 25` and no speculation, the ladder
returned **1280 of 1280** requests byte-identical to the sequential oracle at c64,
on the suite selected for being the most divergence-prone, against 35/1280 and
24/1280 in two matched barrier arms. Poisson `P(0 | 30) = 1.5e-13`; the harness
certified it `output-identity-qualified` on its own. Cost is 14.2% of throughput.
On the speculative lane the same stagger does not give exactness (44.61%
divergent) but makes *which* slot diverges reproducible — modal minority-slot-set
recurrence 33.8% under a barrier against 95.45% under stagger, which answers the
9B lane's open "slot index or step membership" question.

Single-stream generation is fully deterministic here: the `g1`, `g2` and `g3`
oracles are identical 64 of 64 on both lanes across three fresh servers. The whole
phenomenon is a concurrency artifact, and it is removable rather than intrinsic.

**Replicated.** The `r1` arm repeated it on a fresh server: 1280 of 1280 again,
1474.0 tok/s against 1474.3. The speculative lane replicated to the individual
request — 709/1280 exact in both, 42 bistable slots, 28 oracle-on-minority, 44
sites and 95.45% slot recurrence in both — so with deterministic arrival the whole
ladder outcome is reproducible across independent servers, not just the exactness.

That gives the cleaner statement: **deterministic arrival gives deterministic
output**, and the lanes differ only in what that output equals. At MTP0 it equals
the single-stream oracle; at depth 3 it is equally reproducible but different from
it. Speculation does not reintroduce randomness, it moves the deterministic answer
away from the sequential one.

All of that has since closed. `r2` is exact on the unbiased full suite, `r3`
shows 5 ms is as exact as 25 ms at 1.0% cost, `w1`/`w2` show it on two cards, and
chain 10's `x1` shows it at **every rung**: TP2 with a 5 ms stagger is 160/160,
320/320, 960/960 and 1280/1280 at c16, c32, c96 and c128 — 2720 of 2720 requests,
at 3022.0 tok/s for the top rung against 3103.9 unstaggered. `x3` shows the two
levers compose: with `max_num_batched_tokens` 1024 the MTP0 recipe is still
1280/1280 (1699.7 tok/s), and on the speculative lane the pair reads 18.67%
divergent against 49.53% for the stagger alone — though oracle-free minority rises
from 5.28% to 9.90%, so the two thresholds move in opposite directions. Other
models remain unmeasured.

**The divergence sites are exact ties — measured, not inferred.** At
`cache-c056` index 50 the sequential pass assigns `" HTTP"` and `" Redis"` the
identical logprob `-1.670863151550293`, and the concurrent pass separates them by
one quantum and takes the other. Across seven divergences at four sites the oracle
gap is min 0.0, median 0.0, max 0.015625.

That answers the mechanism question and closes several loose ends at once. A tie
is a deterministic property of the weights and the prefix, which is why sites
survive reboots and never produce a third branch. It is why **five
row-invariance interventions were all nulls** — they change which arithmetic runs
and cannot remove a tie, so any difference of any magnitude still resolves it, and
making one op invariant hands the decision to the next. And it is why staggered
admission works instead: it makes the perturbation reproducible rather than trying
to eliminate it.

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

## What the campaign ran

Nine chained runners, 31 arms, 07:26 finish, no hardware aborts; then chain 10
(`gen`, three arms, 18:46-19:27) and chain 11 (`rowchunk`, three arms, from 20:00).
Scripts in `scripts/run-20260909-*`, wrappers at
`/mnt/fast-ai/bench-results/qwen35-4b-{exhaustive,fragile,gdn,stagger,depth,margin,shallow,mbase,tp2stag,gen,rowchunk}-20260909-wrapper.log`.
A chain sleeping in its wait loop can be stopped by pid, edited and relaunched;
that is how arms were inserted mid-campaign without disturbing the cards.

**Eliminated by measurement**, each by moving its own knob and watching nothing
change: the GDN speculative group size (three arms over a fourfold range), the
capture ceiling (doubled), the determinism pad (20 passes, and the site set
unchanged), and the verify batch's row count (flat across depths 1, 2, 3 and 6).

**The deployable configuration.** Two cards, no speculation, 5 ms admission
stagger: **2711 tok/s at c64, byte-identical to single-stream output**,
harness-certified `output-identity-qualified`. One card is 1701.5 tok/s at the
same exactness. Six arms show it; 5 ms is the floor, 2 ms leaves 0.94% and 1 ms
leaves 2.89%.

**Free levers found along the way.** `max_num_batched_tokens` 512 to 1024 halves
depth-3 divergence at c64 at slightly better throughput. Depth 2 is level with
depth 3 single-user and 14% better at c64. And a warning: a divergence rate is not
a property of (model, depth, concurrency) — two servers differing only in
`max_num_batched_tokens` differ 2.5x at the same rung.

**The throughput dip is at c36, not c40, and is not padding.** `x2` mapped
c32-c64 at every rung with every rung graph-captured: 1593 tok/s at c32, **1253 at
c36**, then 1360, 1438, 1508, 1623, 1727 — a 21% cliff at 32→36 and a linear
recovery to c64. Padding to a captured shape is eliminated by construction. The
one thing in the server with that shape is the R224 overlay's 32-row FP16 linear
chunk: above 32 sequences the tail piece holds 4, 8, 12, 16, 24 then 32 rows and
throughput tracks it, and at depth 3 (four rows per sequence) the only rungs that
dip, c36 and c44, are the only two leaving a 16-row tail. **Chain 11 tests it**:
`y1` reruns x2 with the chunk disabled, `y2` predicts the next cliff at c68 with
it on, `y3` checks the exact recipe survives the change. Until `y1` reports this is
a hypothesis. If it holds it applies to every lane running R224, and every
published exact-throughput rung (16, 32, 64, 96, 128) happens to sit where the
cost is zero. Also still unexplained: the c16 identity step survives the
elimination of both candidates that sat at 16 sequences.

## Scope

In-repository evidence only, by agreement: no package or catalog updates, no
LocalMaxxing submission. Results live in this lane's `data/` and `notes/`, plus
four lab-level notes under `notes/`.

Two findings are packaging-relevant whenever the owner wants them:
`families/qwen-4b.json` still lists `tp: [1]` and context `[1024, 8192]` while TP2
is measured lossless on the strict suite, at 32K context and under concurrency;
and depth 2 may be the better operating point for any server with load.
