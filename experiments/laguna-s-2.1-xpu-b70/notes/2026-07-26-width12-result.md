# Laguna — width 12 result: 100.524890 tok/s, exact, batched topology restored

Date: 2026-07-26 America/Toronto. Preregistration:
`2026-07-26-width12-preregistration.md`, written before the run.

## Result

| | width 8 control | width 12 candidate |
| --- | ---: | ---: |
| scored median tok/s | 94.822732 | **100.524890** |
| bitwise exact vs q=1 | 13/13 | **13/13** |
| topology, all ranks | 146/145 | **146/145** |
| depth | 7.000 | 11.000 |
| emitted per cycle | 3.7010 | 3.9552 |
| acceptance | 38.59% | 26.87% |
| derived cycle | 39.03 ms | 39.35 ms |

**+6.01%** over the same-session control, valid on every gate: cache-zero, each
prompt run once, one active generation, clean idle either side, clean shutdown.

Every preregistered expectation held. Topology came in at exactly 146/145 on all
four ranks for both capture and replay, emitted per cycle landed at 3.9552
against a predicted 3.96–4.01, and the scored median fell short of 102 as
predicted.

## What this settles

**The three batched-M1 bound fixes work.** The prior width-12 attempt produced
685/684 — `(M−1)` extra eager breaks per layer, the signature of per-row
serialization — and then exhausted device memory inside a Level Zero replay and
took the host down. The same width now produces the audited topology exactly.
That was the outstanding untested hypothesis in this lane and it is now closed.

Per-position acceptance decays properly — 1166, 844, 632, 496, 402, 331, 252,
203, 171, 139, 113 — which is what distinguishes this from the rejected
draft-capture candidate, where acceptance barely decayed at all and every prompt
was wrong.

## Cycle time is not flat in M

Two measured points on the same build put the derived cycle at 39.03 ms at width
8 and 39.35 ms at width 12: **+0.81%**. Prior projections assumed flat cycle
time. It is not flat, and that matters for what comes next.

## Where 102 now stands

The gap from 100.524890 is **+1.47%**.

Fitting conditional acceptance to both measured points gives p = 0.7598 at depth
7 and 0.7560 at depth 11, a decay of −0.00096 per step. Extrapolating:

| candidate | emitted/cycle | assumption | projected tok/s |
| --- | ---: | --- | ---: |
| depth 15 (M=16) | 3.9921 | cycle grows another 0.81% | **100.65** |
| depth 15 (M=16) | 3.9921 | cycle flat | 101.46 |
| **11-node tree (M=12)** | 4.0831 | same cycle as measured width 12 | **103.78** |
| 15-node tree (M=16) | 4.3259 | cycle grows 0.81% | 109.07 |

**Depth alone no longer reaches 102 at any available width.** Depth 15 adds only
+0.93% emitted per cycle over depth 11 — the geometric tail is spent — and the
measured cycle growth cancels most of it. Even the flat-cycle case lands at
101.46.

The 11-node tree is the smallest change that projects past the goal, and it runs
at width 12, whose topology and exactness are now measured rather than assumed.
Its projection carries the known caveat that DFlash cannot condition a draft on
the path, which overestimates off-spine nodes by roughly 5%; 103.78 less that
margin still clears 102, but not comfortably.

## Next

The tree at width 12. Its logic layer is complete and tested; the wiring left is
the `write_slot` KV scatter and the drafter top-2 read. Width 16 is not worth a
leg on its own against these numbers.
