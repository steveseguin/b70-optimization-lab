# Laguna — draft graph capture is a false win: 198.7 tok/s with zero exactness

Date: 2026-07-26 America/Toronto

Status: **candidate REJECTED.** `VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=1` remains
default-off. The approved record stands at **94.920039** tok/s; this session's
width-8 control re-established it at **94.822732**.

## The result, and why it is not a result

| | control (draftgraph=0) | candidate (draftgraph=1) |
| --- | ---: | ---: |
| scored median tok/s | 94.822732 | **198.702807** |
| bitwise exact vs q=1 teacher | **13 / 13** | **0 / 13** |
| acceptance rate | 38.59% | **95.91%** |
| accepted per cycle | 2.7010 | 6.7138 |
| per-position accepted | 1272, 936, 710, 566, 468, 391, 300 | 847, 837, 830, 824, 820, 818, 818 |

The throughput more than doubled and **every one of the 13 prompts produced the
wrong tokens**. This is a broken-output artifact, not a speedup, and it must
never be cited as progress toward 102.

## What actually happened

The per-position acceptance is the tell. Real acceptance decays with depth
because each position must match: the control falls 1272 → 300 across seven
positions. The candidate barely decays at all, 847 → 818 out of 863 drafts, and
accepts 95.91% of drafted tokens. The verifier is rubber-stamping. It is not
drafting better; it has stopped checking.

The target's own audited topology was fine — 146 graphs / 145 eager breaks
captured *and* replayed on all four ranks — so the two graph wrappers really are
independent, as intended. The damage is to the data dependency between drafter,
verifier, and the accept path.

## The reasoning error this corrects

I argued repeatedly that capturing the drafter **could not** affect correctness,
on the grounds that the verifier emits the target's greedy continuation whatever
the drafter proposes, so a captured draft could only move the acceptance rate.
That was wrong, and it was the single claim I leaned on hardest to rank this
candidate first.

The flaw: graph replay makes the drafter's output buffers static and replays a
recorded sequence. Exactness does not depend only on the verifier *deciding*
correctly — it depends on the verifier *reading the tokens that were actually
proposed this cycle*. Capture broke that live data flow, and once the comparison
reads stale or aliased buffers, acceptance becomes unconditional. "The verifier
guarantees correctness" is true only while the verifier's inputs are live.

The exactness gate caught it immediately, at zero cost, which is exactly why the
gate exists and why a tempting number never substitutes for it.

## Where this leaves the cycle-time axis

The measured 8.694 ms drafter cost inside a 39.03 ms cycle is still real, and
still 22.3% of the cycle. What is now disproved is that a wholesale breakable
capture of the drafter is a safe way to claim it. Any future attempt has to keep
the drafter's per-cycle outputs live to the verifier and re-prove 13/13
exactness before its timing means anything.

## Next

Width 12 as one bounded structural test, then width 16. Both act on the
acceptance axis and leave the draft path untouched.
