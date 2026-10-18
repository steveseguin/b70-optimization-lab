# Packet58h one-card MTP feasibility — closeout

<!-- campaign-closeout -->

## Question and identity

Can the frozen packet58g one-card Unsloth IQ3 target add the existing
target-verified one-token MTP draft, retain packet49 arithmetic and BF16 KV,
fit with memory margin, and predict at least 28.8 tok/s? CPU-only analysis on
steve-b70s, October 18 UTC / October 17 Toronto, 2026.

## Outcome

**No build.** Device accounting fits, but retained timing admission needs about
121.65 GB available RAM and fails every recorded 58g snapshot. The primary
cross-run timing model predicts 24.62 tok/s. Its most optimistic device-only
sensitivity reaches 28.86 with effectively no overhead allowance; adding the
existing rejection-weighted restore proxy reduces it to 28.76. These are
calculations, not new speed or quality measurements.

## What worked

The complete one-card census reconciles across KD, WS and WS128x. The draft
head can share existing rows for zero additional weight bytes. Exact retained
draft allocations and full private row reservations fit inside device bounds,
including existing control/workspace allowances without double charging.
Compressed input snapshots make the CPU result independently reproducible.

## What failed or remains uncertain

Sharing the cache does not remove the separate 3.146 GB draft expert bank.
The draft cost, acceptance and M2 ratio are transfers from two-card evidence;
one-card causal verification, draft feedback and cache interference were not
measured. WS128x uses zero-copy misses and is an exactness window. No runtime
was built, no new arithmetic/state identity was established, and no new
submit-time extent or teardown gate was exercised.

A passive check found blocks 53–56 offline and 57 online, differing from the
brief's 10 GiB exclusion. It remains untouched and is not a source of admitted
extra RAM. No recovery or operational action belongs to this closed CPU arm.

## Evidence and patches

[Analysis](FEASIBILITY.md), [numbers](feasibility.json), [source/archive
manifest](inputs.json), [reproducer](feasibility.py), [negative index](DO-NOT-REPEAT.md),
[task note](../../../../notes/2026-10-18-own-runtime-packet58h.md).
No implementation patch exists because feasibility did not pass. Original
packet58g and all other frozen trees remain unchanged by this work.

## When to revisit

Require both a credible faster causal M2 mechanism, including state and cache
costs, and a complete host admission that retains the exclusions and reserves
with margin. The present zero-overhead verify ceiling is 60.27 ms, before
charging rejection repair. Re-account both gates before building; do not
repeat this same draft/cache composition just because the head is shared.
This closes one proposed arm, not the one-card optimization lane.
