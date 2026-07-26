# Laguna — the rank-2 rescue rate, measured at width 12

Date: 2026-07-26 America/Toronto. Diagnostic only; no throughput claim.

## Why this was measured before building

The tree's projection rested on one quantity taken from a width-8, depth-7 probe
and extrapolated: when the top-1 draft is rejected, how often is the target's
actual token the drafter's second choice? The remaining tree work is hours in
the exactness-critical path, so it was worth one leg to check the number at the
width that matters.

## Result

From 2,056 usable cycle pairs at width 12, depth 11:

| quantity | measured |
| --- | ---: |
| position-0 accepted (rank-1 hit) | 1468 = **71.40%** |
| position-0 rejected | 588 = **28.60%** |
| of those, rescued by the drafter's rank-2 | 257 = **43.71%** |

The width-8 extrapolation was 43.2%. The measured width-12 value is **43.71%**,
so the assumption holds.

The recorder joins each cycle's top-2 against the *next* cycle's entry state,
which reports the previous cycle's outcome. A cycle that rejected everything
rejected at position 0, and the token it then emitted is the target's own token
at that position, which is what the rank-2 candidate is compared against.

## What it implies

Row count is unchanged: an alternate replaces a spine node rather than adding a
row, so the verifier stays 11 wide and cycle time is unchanged apart from the
private-block copies, which are one strided operation of roughly ten
microseconds against a 39.35 ms cycle.

| shape | accepted/cycle | emitted/cycle | projected tok/s |
| --- | ---: | ---: | ---: |
| spine depth 11 (measured) | 2.9552 | 3.9552 | **100.52 measured** |
| spine 10 + alternate at depth 1 | 3.0290 | 4.0290 | **102.40** |
| spine 9 + alternates at depths 1, 2 | 3.0556 | 4.0556 | **103.08** |

The trade is explicit: the depth-1 alternate gains 0.1200 accepted tokens per
cycle and gives up the deepest spine node worth 0.0461, netting 0.0738. The
depth-2 alternate gains 0.0876 and gives up 0.0610, netting 0.0266. A third
alternate would give up 0.0808 to gain less, which is why the shape stops at
two.

## Standing

Both shapes clear 102 on measured inputs rather than extrapolated ones. That is
a projection, not a result: it assumes the rescued tokens are accepted by the
same exact verification the chain uses, which is exactly what the 13/13 bitwise
gate will decide.

Best measured result remains **100.524890** tok/s.
