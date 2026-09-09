# The divergence rate partly measures where the oracle landed

Found while trying to explain why one 4B arm looked twice as deterministic as
another. It applies to every identity ladder this lab runs.

## The problem

A ladder reports `n/N exact`: how many concurrent responses match a **sequential
oracle** generated on the same server. That oracle sits on the same fragile sites
as every other response, and at a bistable site it takes one branch or the other.

**It is not random.** Measured across the `g1`, `g2` and `g3` arms — three fresh
servers — the sequential oracles are identical 64 of 64 on both the MTP0 and the
depth-3 lane. Single-stream generation on this stack is deterministic, with and
without speculation, and the divergence is purely a concurrency phenomenon. So the
oracle's branch is a **deterministic function of the configuration**: it does not
vary between runs of the same configuration, and it can move when the
configuration changes.

When the oracle lands on a site's **minority** branch, every concurrent request
that takes the majority branch is counted as divergent. The rate at that site
inverts: a site where 80% of runs agree with each other is reported as 80%
divergent.

So the rate mixes two things: how often the server produces the minority branch,
and which branch that configuration's sequential path takes. The second is stable
within a configuration and can shift when one changes — which is exactly the
situation in an intervention comparison.

## How large the effect is

Same model, same suite, same rung, matched at six passes:

| arm | oracle-based | oracle-free | bistable prompts | oracle on minority |
| --- | ---: | ---: | ---: | ---: |
| `f1` c64 | 14.06% | 6.70% | 15 | 6 |
| `f2` c64 | 14.84% | 6.92% | 17 | 8 |
| `f4` c64 | 5.21% | 3.79% | 8 | 1 |

`f1` and `f2` report roughly double their oracle-free rate because their oracles
sit on the minority branch at six and eight prompts. `f4`'s oracle sits on the
minority branch once, and its two numbers nearly agree.

At full power the same shape holds for `f4`'s other rungs: c96 reads 6.77%
oracle-based against 3.57% oracle-free with six oracle-minority prompts, and c128
reads 6.25% against 4.02% with six.

## The oracle really does move

This is not hypothetical. Comparing the `f1` and `f4` oracles directly, **11 of 64
oracle responses differ**, and at six of eight high-rate sites the oracle token
itself changed side:

| site | `f1` oracle | `f4` oracle |
| --- | --- | --- |
| `cache-c056` @50 | `" HTTP"` | `" Redis"` |
| `capacity-c062` @54 | `" resource"` | `" constraint"` |
| `cache-c048` @89 | `" comes"` | `" arrives"` |
| `rollback-c010` @112 | `" hang"` | `" leave"` |

`f1`'s highest-rate sites are simply **absent** from `f4`'s site list, because
`f4`'s oracle moved to the branch its concurrent runs already preferred, so those
requests stopped counting as divergent.

## The better instrument

Count **minority-branch samples against each prompt's own modal completion**,
with the oracle included as one more sample. It needs no reference response, so
nothing depends on which branch a single draw took, and it is comparable across
pass counts.

`summarize-arm.py` now reports it as `min%`, alongside `bist` (how many prompts
showed more than one completion) and `oMin` (how many had the oracle on the
minority branch). A large gap between `div%` and `min%` means the arm's oracle
was unlucky, not that the server was worse.

## What it does and does not change

**It does not invalidate the gates.** G1, G2 and G3 ask whether two runs are
byte-identical, which is a different and still-correct question, and the strict
suite is unaffected. "Lossless" claims that rest on exact gates stand.

**It affects rate comparisons between arms, but only when their oracles land
differently.** Any two arms that regenerated their own oracles can differ in
reported rate purely because their oracles drew differently. That regeneration is
required by AGENTS.md rule 2 — an oracle is bound to its arithmetic — but the
consequence for the *rate* was not on record.

**Checked, and the 9B powered comparisons survive it.** The five 20-pass
`identitypower` arms at c64 read:

| arm | `div%` | `min%` | oracle on minority |
| --- | ---: | ---: | ---: |
| `p0` | 6.17% | 2.46% | 4 |
| `p1` | 6.25% | 2.68% | 4 |
| `p2` | 6.09% | 2.23% | 4 |
| `q1` | 6.25% | 2.83% | 4 |
| `q2` | 6.56% | 2.68% | 4 |

Every arm's oracle sat on the minority branch at exactly four prompts, so the
artifact is a near-constant multiplier of about 2.4x across all five and the
ratios between them are preserved. Those comparisons are not distorted. The
confound bit in `f1` versus `f4` because there the oracles landed differently —
six oracle-minority prompts against one.

So the rule is not "past rate comparisons are wrong"; it is "a rate comparison is
only safe when both arms' oracles landed similarly, and `oMin` is what tells
you". Report it.

**It changes the reading of `f4` versus `f1`, but less than first stated.** An
earlier version of this note said the improvement was about half artifact and
half real. Quantified against `f1` at full power — 99 minority samples of 1344,
7.37% — `f4`'s 17 of 448 is significantly lower (Poisson P(<=17 | 33.0) = 0.0017).
The decomposition is:

| | factor |
| --- | ---: |
| oracle-based reduction, 13.28% -> 5.21% | 2.55x |
| oracle-free reduction, 7.37% -> 3.79% | **1.94x**, p = 0.0017 |
| the oracle artifact | 1.31x |

So most of the reduction is real and the artifact accounts for the remaining
1.31x. `f4` genuinely produces the minority branch about half as often. The `mb`
arm isolates whether that is the capture ceiling or the scheduler settings, and if
it is the latter it is an easy operational win.

One caution on a tempting sub-analysis: nine prompts bistable in `f1` are
monomorphic in `f4` at matched passes, but that set was selected *by* being
bistable in `f1`, so regression to the mean inflates it. The pooled minority
fraction above is the unbiased comparison; the per-prompt list is not.

## Recommendation

Report `min%` beside `n/N exact` in every identity result. Where an intervention
is being compared, prefer `min%`, and treat a `div%` change unaccompanied by a
`min%` change as the configuration having moved its own sequential reference
rather than as a finding.
