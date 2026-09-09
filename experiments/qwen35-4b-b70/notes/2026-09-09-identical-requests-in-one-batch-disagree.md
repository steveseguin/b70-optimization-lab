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
| `fragile-f0` | 23/240 (9.6%) | **74/240 (30.8%)** |
| `fragile-f1` | 23/240 (9.6%) | **100/240 (41.7%)** |

The MTP0 column is the 2026-09-08 measurement. The depth-3 column is new, and it
matters because it is where the lane actually serves.

Two further properties:

- **Always exactly two distinct outputs**, never three, from five or six copies.
  The distinct-output histogram over all 1920 copy-groups is `{1: 1491, 2: 429}`:
  a group of identical copies produces either one completion or exactly two, and
  a third was never observed. That is the strongest single statement of the
  binary-fork model in this campaign, because it is 429 independent chances for a
  third branch to appear and it never did.
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

## What it rules out

Batch composition is identical for every copy in a group — they are in the same
batch, in the same steps, with the same neighbours. Prompt text is identical.
So neither content nor batch shape decides which branch a request takes.

That is why the determinism pad cannot help, and the measurement agrees: padding
decode row counts to fixed tiers costs 11.7% at depth-3 c64 and leaves the site
set, the per-site counts and both divergence measures unchanged. The pad makes
the batch *shape* constant; the disagreement here happens at constant shape.

More generally, any intervention whose mechanism is "remove dependence on how
many rows are in the batch" is aimed at the wrong thing for this phenomenon.

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

`g3`, which staggers arrivals by 25 ms, is a real manipulation of this variable:
it changes arrival order and step composition rather than trying to pin a row.

## Only the 9B has verbatim data so far

Scanning every lane, the 9B fragile campaigns are the only verbatim runs on disk;
the 27B and 4B have none. Chain 2's `g1`, `g2` and `g3` arms are verbatim and will
give the first 4B copy-groups, so this can be checked on a second model tonight.

## Where this leaves the mechanism

Established: the fork is between two whole continuations; the sites are stable
across days, reboots, compilation modes and the pad; the direction flips when the
arithmetic changes under TP2; and now, identical requests in one batch take
different sides.

So whatever chooses the branch is neither the prompt, nor the batch shape, nor
the batch composition. It is something that differs between two identical rows of
the same step — reduction order, work-group scheduling, or an atomics ordering
inside the kernel are the obvious candidates, and this data cannot distinguish
them.

The margin probe in chain 4 is the next useful measurement: if the logit gap at
these sites is at or near zero, then any of those candidates suffices and the
question becomes which one, not whether.
