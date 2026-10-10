# Packet 131: memory admission for the 145-frame cone graph

The useful candidate moves full display decode to the exact xpu:2 replica and
releases eligible unused allocator blocks only when the cone's fresh memory
admission needs them. Default off preserves130. No GPU work or launch was
performed; the coordinator retains the live129 server.

The [xpu:3 inventory](2026-10-10-xpu3-residency-145.md) corrects two assumptions.
The cone already captures only `forward_pre_diffusion`, in a decoder-private
pool, so lowering the soft cap or isolating the pool again cannot save the
first capture. Its121 reserved growth is exactly3,430,940,672 bytes; the19/16
squared estimate is4,838,162,432 bytes (4.505890GiB). That is not an exact145
measurement or a proven peak bound. Secondly, qualification retains full
card3 reference decodes. Moving display alone leaves their allocation cache
behind; the saved124 qualification tail needs3.345680GiB recovered for the
estimated graph plus screening.

The selected option requires5GiB capture allowance,9GiB decode floor and0.75GiB
screening before first capture. Later cones require9.75GiB because the graph
is resident. A failed reading permits one process-wide empty_cache call and
a fresh reading. Insufficient physical free refuses and latches; no retry,
fallback, memory credit from counters, tensor eviction or lower floor. The
first capture must be forward_pre_diffusion, keep all arithmetic proofs,
stay within the observed5GiB growth allowance and retain9.75GiB free afterwards.
The allowance is checked after capture and is not a hard allocator limit.

The new scope is fixed145/frame/dg1/cone/bo1/pa1/two-way20-28, serial eager
display2, legacy auxiliaries, fingerprint/full snapshots and read-ahead0.
GC60, immutable digest caching and idle maintenance remain usable in that
explicit scope. Packet130 allocator mode stays off and pool cap stays unset.
Every mode is bound through run naming, plan, server options, decode records,
qualification verdict and client expectations. All nine native cross-card
full-image comparisons and every stream display==cone byte check survive.
No lossy option or native source arithmetic changed.

The [snapshot audit](2026-10-10-continuation131-snapshot-schedule.md) measures
418 receipts and2,508 snapshots. In matched40-chunk windows the first three
snapshot inspections total120.782–124.793ms;129 gives122.408ms. The on-chain
option removes12 synchronization calls on cards0/1/2 across the two A sites;
it removes no tensor, state, residency, memory-floor or byte checks. Their
measured memory sections total1.729–1.789ms; controller barrier time is not
separately recorded. A0.12-second saving cannot be claimed. Qualification,
every20th chunk and near-floor escalations remain full. The option stays off
and outside the new scope; combining it with digest/GC60 needs owner review.

The [contract](../recovery/20261010-continuation131-stream/CONTRACT.md) and
[future launch](../recovery/20261010-continuation131-stream/LAUNCH.md) give exact
settings. Conditional cadence target is5.25–5.35s per6s (0.875–0.892s/s),
transferring the121 graph gain. Native capture peak, reclaim, phase headroom,
full output equality and repeated speed are still unmeasured. Audio-only
placement would move0.339622GiB, insufficient alone; its isolated time and
workspace are not measured by the bundled123 auxiliary arm.

The [build receipt](../data/resume-20261008/continuation131-build.json) records
sealed parent130, manifest and inner plan identities, exact final CPU suite
counts, recursive verification and scratch cleanup. Tests include actual tiny
CPU decoder graph mechanics with fake capture backend, admission boundaries,
malformed evidence, three-chain runtime flow and client checks. They establish
CPU behavior only. All Python uses pinned bin/python -B, nice19 and OMP/MKL2.
No GPU/model server/check-only, port8188 or unit operations, process signals,
host setting changes, existing-run writes or ltx-stream writes occurred.
