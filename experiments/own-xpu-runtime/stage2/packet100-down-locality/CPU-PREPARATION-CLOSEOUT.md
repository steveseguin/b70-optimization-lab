# Packet100 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can workgroup order or a lossless packed-byte transpose improve routed IQ4_NL
DOWN locality? Packet97 source/binary lineage, Flash-Next compressed IQ3 lane,
`iq3-p49-split32-v1`, full 16-bit KV, 2560x640 DOWN, B70, October 18.

## Outcome

Two CPU-exact candidates plus production are built and sealed. All 34 startup
checks, allocation/mode refusals, Python checks and temporary plans pass.
No GPU ran. No performance result exists. Device execution is blocked by
missing raw route vectors in the retained packet77/86 receipts.

## What worked

Both mechanisms preserve weight extent and exact FP32 accumulation. The new
layout aligns every 16-byte code vector. Offline linked code retains 79 load
lines and 128 GRFs, with no scratch loads/stores. Production and both candidates
are bit-identical within and across GNU/Intel repeats. All composition corners
reach their intended kernels and fit the unchanged actual arenas.

## What failed or remains uncertain

The first copy omitted an included .inc file, then the extracted IQ4 loop
needed its unchanged Packed=false compile-time constant; both failed at compile
time and were fixed before the first build milestone. Full-size testing led to
explicit unsupported-mode refusals before allocation. A dependent micro build
was attempted before its new engine receipt existed and correctly refused.
The seal's initial fixture-count assertion was corrected from 72 to the actual
36 cases per run (72 across two repeats). No correctness tolerance was added.

A bounded scan of 3,516 raw route files found zero matches for 576 distinct
receipt hashes (1,152 recorded rows across 24 archives). Synthetic or miniature
routes cannot substitute. Cache level, TLB behavior, physical DRAM page hits,
prefetch distance, device exactness and performance remain unmeasured.

## Evidence and patches

[CPU bytes](evidence/cpu-byte-identity.json), [full startup](evidence/full-shape.json),
[offline report](register-report-offline.json), [Python checks](evidence/python-tests.json),
[route inventory](evidence/route-inputs.json), [queue plans](evidence/queue-plans.json),
[final checks](evidence/final-verification.json), [source](p100_down.hpp),
[retention](RETENTION.md). Original packet97/99 sources remain untouched.

## When to revisit

Recover receipt-matching route payloads, then run the bounded micro on lane B
under normal coordinator admission. Only >=15% kernel-time winners proceed to
separate B grids and A confirmations. Records require the full later chain on
lane A; this CPU-only brief does not authorize any device run.
