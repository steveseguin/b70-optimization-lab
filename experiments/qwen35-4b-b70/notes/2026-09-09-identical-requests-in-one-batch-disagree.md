# The within-batch disagreement, extended to the speculative lane

**This phenomenon is not new here.** The 9B lane established it on 2026-09-08 in
`experiments/qwen35-9b-b70/notes/2026-09-08-identical-prompts-in-one-batch-diverge-from-each-other.md`,
which reported 23 of 240 copy-groups disagreeing in each of the `f0` and `f1`
arms, drew the conclusion that "the result depends on which row a request
occupies" rather than on how many rows share the step, and stated the same limit
about step composition that is restated below. It also recorded the two
shape-invariance interventions as flat at that power and told the lab to stop
testing shape-invariance against this metric. That note found it; this one
extends it.

Reproducing its numbers exactly on the lane it used — MTP0 — gives 23 of 240 in
both arms, 9.58%, with divergence 1.80% and 1.88% and throughput 2095.3 and
728.9 tok/s against its 2093.6 and 728.9.

**What is new here** is the same diagnostic applied to the *speculative* lane of
the same campaigns, which that note did not examine, plus the histogram result
over the whole corpus and the connection to tonight's 4B pad null.

## The observation

A verbatim ladder fills its slots with byte-identical copies of the same prompt.
Pooled across every verbatim run on disk and both lanes, **429 of 1920
copy-groups (22.3%) contain copies that disagree with each other inside a single
batch** — same text, same batch, same steps, different completions.

Split by lane, the speculative half is three to four times worse:

| campaign | MTP0 lane | depth-3 lane |
| --- | ---: | ---: |
| 9B `fragile-f0` | 23/240 (9.6%) | **74/240 (30.8%)** |
| 9B `fragile-f1` | 23/240 (9.6%) | **100/240 (41.7%)** |
| 4B `g1` | pending | **216/320 (67.5%)** |

The MTP0 column is the 2026-09-08 measurement. The depth-3 column is new, and it
matters because it is where the lane actually serves. The 4B replicates the
phenomenon on a second model at a higher rate still.

The 4B `g1` arm also confirms the fragile suite works as designed: 53.98%
divergence against the full suite's 13.28% at the same rung, a fourfold
concentration of events for the same card time, which is what
`build-fragile-suite.py` was built to buy.

Two further properties:

- **Every site is binary, and no true three-way tie has been seen.** The 9B
  corpus histogram is `{1: 1491, 2: 429}` — 429 disagreements, never a third
  output. The 4B fragile arm `g1` then produced `{1: 104, 2: 200, 3: 16}`, which
  looks like a counterexample and is not: all **16 of 16** three-output groups
  diverge at *two* distinct indices, none at one. They are prompts carrying two
  independent binary sites, showing three of the four reachable combinations.

  The indices identify themselves — `cache-c016` at 26 and 50, `capacity-c022` at
  17 and 93 — and those are exactly the two prompts already known to carry a
  second site, from the TP 2x2 test where they were the pair that failed to close
  at precisely those positions. So the corrected statement is stronger than the
  original: a *site* is always binary, and a prompt's number of distinct outputs
  is 2^(number of its sites).
- **Almost always exactly one copy in the minority.** A typical group reads
  `majority slots [2, 14, 26, 38, 62], minority slot [50]`.

## The two interventions are flat at MTP0 and look worse under speculation

The 2026-09-08 note compared `f0` (no intervention) against `f1` (row-wise
all-reduce **and** serialised norm) on the MTP0 lane and found them flat: 23
against 24 divergent of 1280, two-sided binomial p = 1.00, and copy-groups
identical at 23 against 23. That conclusion stands exactly as written.

On the speculative lane the same pair is not flat, and all three measures move
the same way — against the intervention:

| measure | `f0` | `f1` |
| --- | ---: | ---: |
| oracle-based divergence | 33.91% | 35.55% |
| oracle-free minority | 10.64% | 13.54% |
| disagreeing copy-groups | 74/240 | 100/240 |
| throughput | 1405.9 | 1288.6 tok/s |

The oracle artifact is matched (`oMin` is 23 in both), so the comparison is fair.
None of the three is individually decisive — the copy-group difference gives a
naive z of 2.47, and groups inside one pass share a batch so the effective sample
is nearer 20 than 240 — but three independent measures agreeing in direction, at
an 8.3% throughput cost, is worth recording. Combined with the 65% throughput
cost the same pair carries at MTP0 (2095.3 to 728.9 tok/s), there is no reading
on which these two interventions are worth enabling.

This is an observation on the 9B lane from a 4B campaign's tooling, not a
conclusion of that lane's owner, and it is offered as such.

## A framing this note previously got wrong

An earlier version argued that copies in a group "are in the same batch, in the
same steps, with the same neighbours", and concluded from that that batch shape
cannot decide the branch. **That is contradicted by measurement.**
`2026-09-08-three-candidates-eliminated-for-the-two-card-divergence.md`
reconstructed absolute per-token arrival times and found copies of one prompt
routinely spread over **2.7 to 2.9 decode steps**, whether or not they disagree —
"copies of one prompt are simply not in the same step, ever", which as that note
says retires the same-batch-different-row framing. It also eliminated slot index
as a predictor: minority slots are scattered and nothing recurs.

So copies do see different step compositions, and the within-batch disagreement
does not by itself rule out shape or composition dependence. The claim is
withdrawn.

## Why the pad fails, on the 9B lane's current account

An intermediate version of this note credited the FP16 vocabulary projection's
33-row strategy switch. That was reading one note in a chronology and stopping.
The lane went on to **test** it: `2026-09-08-the-divergence-originates-upstream-of-the-vocabulary-projection.md`
chunked the projection to 32 rows — value-preserving by construction, verified
in-container to make every row's logits bitwise equal to its single-row value —
and found no effect, 22 against 20 divergent of 1280, `p = 0.88`. The projection
is row-dependent *and* is not the cause; the hidden states arriving at it already
differ.

Their settled position, from
`2026-09-08-a-lockstep-batch-is-deterministic-the-ladder-is-not.md`, is better
than any single-op story:

- a batch of **constant composition is deterministic** — 64 identical prompts in
  lockstep gave 64 identical outputs at 64 rows, on two cards, eager *and* under
  `FULL_DECODE_ONLY` capture;
- the divergence needs the composition to **vary**, which is what a real server
  does and what the ladder does, its requests drifting about three decode steps;
- so **every row-count-dependent op contributes** — the norm from 16 rows, the
  projection from 33, and whatever else in the body shares the property — and
  fixing them one at a time cannot move the number.

That explains the pad exactly, and it explains it better than a single-op account
would: the pad is one more row-count intervention in a model where several ops
carry the dependence. Four powered arms had already found this; tonight's is the
fifth, on a second model.

It also means the graph-capture question is settled from their side and not mine:
capture was tested directly in the lockstep probe and did not reproduce the
divergence.

## What it does not settle, and why

The tempting next step is to read the slot indices. Which copy lands in the
minority varies between passes — `monitoring-c020`'s minority slot is 50, then
38, then 26, then 50 again; `index-c041`'s is 49, then 1, then 13 — and no slot
dominates the frequency table.

That looks like run-to-run nondeterminism at fixed shape rather than a fixed
row-position effect. **It is not evidence for that, because the `-sNNN` index is a
client-side expansion index, not a server-side batch row.** The harness launches
all requests through a thread barrier, so their arrival order, and therefore
their row assignment, varies from pass to pass. A stable "row 7 always diverges"
effect and genuine run-to-run nondeterminism produce the same client-side
picture.

Separating them needs the server row, which the client cannot pin: the harness's
`--pin-slots` sets an `id_slot` field that vLLM's `OpenAIBaseModel` accepts under
`extra="allow"` and never reads. It is a llama.cpp parameter and is a **no-op on
this path**. The `g2` arm queued in chain 2 will therefore be a replicate of `g1`,
not a slot test, and must be read that way — it is still useful as a same-config
repeat for a noise estimate.

`g3`, which staggers arrivals by 25 ms, is a real manipulation, and under the
lane's settled account it is a **directional test of that account** rather than
just another arm.

The account says a constant-composition batch is deterministic and divergence
requires composition to vary. A 25 ms stagger over 64 requests spreads arrivals
across roughly the whole generation window — a token takes about 31 ms at these
rates — so requests join and leave the batch at more different times than they do
behind a thread barrier. That is *more* composition variance, and the account
therefore predicts **more** divergence in `g3` than in `g1`.

Recorded before the arm runs. If `g3` comes back at or below `g1`, the account's
central variable does not behave monotonically and that is worth more than the
arm was queued to find. If it comes back higher, it is the first evidence that
composition variance can be *dialled* from the client, which would make the
lane's proposed offline drift reproduction easier to calibrate.

Its sibling `g2` is a no-op and is a same-config replicate of `g1`, so the three
together also give a noise estimate for the comparison: `g1` against `g2` is the
null distribution, `g1` against `g3` the effect.

## Only the 9B has verbatim data so far

Scanning every lane, the 9B fragile campaigns are the only verbatim runs on disk;
the 27B and 4B have none. Chain 2's `g1`, `g2` and `g3` arms are verbatim and will
give the first 4B copy-groups, so this can be checked on a second model tonight.

## An independent test of the 33-row threshold, from the 4B at depth 3

The 9B evidence for the threshold is a direct kernel probe plus the observation
that its ladders are exact at 32 users. At MTP0 the row count *is* the user count,
so "32 rows" and "32 users" cannot be separated there.

Speculation separates them. A uniform decode step at depth 3 is four tokens per
sequence, so rows = 4 x concurrency, and a 33-row threshold should appear between
**c8 (32 rows) and c12 (48 rows)** — nowhere near 32 users. The `f3` arm was run
before this note was read, at 8/12/16/20/24/32, and reads:

| rung | decode rows | divergent |
| ---: | ---: | --- |
| c8 | **32** | **0/48** |
| c12 | 48 | 1/72 |
| c16 | 64 | 1/96 |
| c20 | 80 | 11/120 |
| c24 | 96 | 13/144 |
| c32 | 128 | 14/192 |

The only fully exact rung is the only one at or below 32 rows, and the first
non-zero rung is the first one above it. The threshold tracks the **row count**,
not the user count, on a different model at a different depth.

Stated at the right strength: this does **not** identify the vocabulary
projection, which the lane eliminated. What it supports is the broader framing —
that the relevant variable is decode rows rather than concurrent users. Several
ops in the body carry a row-count dependence with thresholds in this region (the
norm from 16 rows, the projection from 33), so a boundary near 32 rows is
consistent with the family rather than with any member of it.

It is one clean rung and 48 requests, so it is corroboration rather than proof.
But it is corroboration of a kind the 9B lane could not produce from its own
ladders, and it costs nothing: the arm was already run.

It also leaves the larger step intact and unexplained. The jump from 1.04% at c16
to 9.17% at c20 is 64 to 80 rows, well above the projection's threshold, so the
projection cannot be what changes there. The two candidates for that step remain
the GDN speculative group of 16 sequences and the capture ceiling of 64 tokens,
which chain 5 separates.

## Where this leaves the mechanism

Established: the fork is between two whole continuations; the sites are stable
across days, reboots, compilation modes and the pad; the direction flips when the
arithmetic changes under TP2; and now, identical requests in one batch take
different sides.

The 9B lane's reading is the one the evidence supports: the FP16 vocabulary
projection changes strategy above 32 rows and moves every row's logits by up to
`3.9e-3`, which flips a token exactly when the top two candidates are within that
of each other. Everything this campaign found about the sites is consistent with
it — the pairs are synonyms, the fork is binary, both branches are whole
continuations, and the direction moves when the arithmetic changes under TP2.

The margin probe in chain 4 is the measurement that would close it. The 9B note
is explicit that its probe used random weights, whose logit margins are enormous,
so it could not show the argmax moving. `probe-tie-margin.py` reads the top-k
logprobs at the actual divergence points on the real model. If those margins sit
at or below `3.9e-3`, the projection's perturbation is sufficient to explain the
flips and the chain closes.
