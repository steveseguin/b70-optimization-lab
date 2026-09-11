# Qwen3.5-4B W4A16 on B70 — lane handoff

Last updated **2026-09-11**. The identity campaign (chains 1-10, 2026-09-09) is
complete. Chains 11-15 (2026-09-09 evening to 2026-09-11 10:49) found and removed
the largest throughput lever on the lane, the R224 32-row FP16 linear chunk, with
a class-consistent replacement (**R293**) that is lossless by every gate. Chain 16
(`r10`, the two-card stagger recipe on R293) is the last arm; see
`notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md`.

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

## Settled 2026-09-09 to 2026-09-11: the FP16 linear chunk was a throughput tax

Every unquantized FP16 linear in this stack (the 1.2 GB vocabulary projection and
the per-layer GDN projections) ran in 32-row pieces so that the oneDNN GEMM stayed
in its single-row rounding class. Each piece re-reads the weight, so depth 3 lost
41% at c32 and 54% at c64, and no-speculation 25-30% above c32 - which is why
"speculation stops scaling at c16" and every published rung above c8 looked the
way it did. Turning the chunk off recovers the throughput and destroys identity
(the compiled path is nondeterministic). The census (`probes/fp16-linear-*`) found
the GEMM has a few M-classes, each position- and pad-invariant, so **R293** pads or
splits every call into one verified class per weight shape:

| | R224 (published) | R293 |
| --- | ---: | ---: |
| G1/G2/G3, TP1 and TP2 | 12/12 | **12/12** |
| one card, no spec, 5 ms stagger, fragile c64 | 1280/1280 at 1702 | **1280/1280 at 2104** |
| one card, no spec, c128 | 1811 | **2520**, 512/512 exact |
| two cards, no spec, c128 | 3104 | **4015**, 512/512 exact |
| one card, depth 3, c64 | 1201 | **1831** |
| single user, depth 3 / MTP0 (strict) | 177.4 / 102.6 | 168.0 / 96.5 |

Two modes on one image, both lossless: `VLLM_XPU_FP16_LINEAR_CLASSPAD=0` keeps the
published single-user headline; `=1` for any server with more than about eight
users. Under R293 depth 3 leads to c16, depth 2 to about c48, no speculation above.
The 5-6% single-user cost is one copy kernel plus a 33-row GEMM per projection per
step, the floor of this design. The 9B and 27B lanes run the same op and carry the
same tax, unmeasured there.

## Settled by the identity campaign (2026-09-09)

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
(`gen`, three arms), chain 11 (`rowchunk`, three arms), chain 13 (`classpad`, R290,
nine arms), chain 14 (`classpad2`, R291, three arms), chain 15 (`classpad3`, R293,
nine arms) and chain 16 (`classpad4`, R293 two-card stagger). Scripts in
`scripts/run-2026091[01]-*`, wrappers at `/mnt/fast-ai/bench-results/qwen35-4b-*-2026090[9]-wrapper.log`
and `qwen35-4b-classpad*-20260911-wrapper.log`. Overlay images R290-R293 in
`experiments/qwen38-27b-b70/docker/`; chain 12 (chunk off) was written and killed
unstarted once y1 showed the chunk is an identity lever.
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

**The throughput dip at c36 was the chunk** (see the R293 section above): `x2`
located it, `y1` showed the whole ramp is the chunk, `y2` predicted and found the
next cliff at c68. Still unexplained: the c16 identity step survives the
elimination of both candidates that sat at 16 sequences.

## Scope

In-repository evidence only, by agreement: no package or catalog updates, no
LocalMaxxing submission. Results live in this lane's `data/` and `notes/`, plus
four lab-level notes under `notes/`.

Two findings are packaging-relevant whenever the owner wants them:
`families/qwen-4b.json` still lists `tp: [1]` and context `[1024, 8192]` while TP2
is measured lossless on the strict suite, at 32K context and under concurrency;
and depth 2 may be the better operating point for any server with load.
