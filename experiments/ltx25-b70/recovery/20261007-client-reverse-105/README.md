# Final client-policy confirmation, reversed order

This standalone CPU plan is the final client-specific comparison. Packet 104
passed its native and optimized exact-output gates; its control-first timing
showed a scoped 6.20% gain. This successor reverses that order once, then closes
the client experiment and moves to sampler critical-path evidence. No runtime
integration, application request, namespace reservation, or reload was performed.

The numerical workload remains identical to 104: ten original ordered fixtures,
original seeds and prompts, window 64, native BF16, 640×384, 25 frames, 8+3 steps,
W2/B1, 23/25 block placement, sampler depth 2 and decoder depth 2. The qualification
basis adds timing order and 104's manifest hash as non-numerical provenance.
The historical 99b constructor graphs remain pinned independently.

[plan_reference.py](plan_reference.py) reconstructs
[candidate-plan.json](candidate-plan.json). Execution order is:

1. Twenty native requests, two independent passes of the ten fixtures.
2. Fourteen candidate requests, emitting ten exact comparisons.
3. Fourteen `timed-fast` requests using `storage-change-only`, emitting ten clips.
4. Fourteen `timed` requests using `always`, emitting the same ten-fixture suite.

Each optimized block has four unscored fills. All four output tensors must
match the independent native references. Names use
`resolution-client-reverse-20261007`. Native indices are 99905000–99905019;
setup captures are 99905030/99905041; candidate, fast, and control start at
99905100, 99905200, and 99905300 respectively. Indices stay monotonic in actual
execution order. Requests retain their phase-derived policies; policy must not
be inferred from a historical index offset.

[schedule.py](schedule.py) produces [setup-schedule.json](setup-schedule.json)
with the same nine setup requests. The first fast request depends on
`barrier:timing`, which depends on `barrier:candidate_verified`. The new
`barrier:fast_verified` depends on all fourteen fast requests, and the first
control request depends on that barrier. There is no preceding
`control_verified` barrier in this plan. The future runtime must verify fast
exactness and source-bound policy readouts, preserve and retire completed tails,
and record a durable fast-verification receipt before admitting control. Both
blocks use the existing timing authority. The final control comparison should
bind and independently reconstruct that fast receipt; it must not require a
control receipt before the first fast block has run.

Only redundant saves of an unchanged client storage ledger may differ. All
source, fault, fresh-free-space and budget checks remain; mutated ledger saves,
request-attempt/completion durability and event flush/fsync remain mandatory.
Setup/native/candidate/control use `always`. The 105 runtime must retain 104's
per-request `client-policy.json` readout and validate its phase, actual policy,
source hash and checkpoint/save/skip counters against each pinned plan row.

The exact budget remains 71 requests, 64 raw captures, cap 64, and 5 GiB writes above
a 50 GiB reserve. Fresh disk and memory admission, immutable successor closure,
namespace collision checks, and 104 predecessor receipts remain runtime gates.
A successful application remains available; faults halt requests without
automatic retries or restart chains. The consumed 104 schedule is not extended.

The two short repeated-workload blocks are not cold-start, endurance, headline,
or record measurements. A single reversed-order result can reduce the obvious
order confound; it does not establish a general confidence interval. Retain the
reduced-write improvement separately from the throughput claim if timing is
inconclusive. Do not add more client comparison pairs by default.

CPU validation: 17 plan tests and 13 schedule tests passed. Tests preserve all 104
per-phase numerical graphs, validate four-fill mappings, reject rehashed policy
and order changes, reject absent/backwards fast barriers, and check namespaces
against sealed 101 through 104. See [cpu-validation.json](cpu-validation.json).
The authored runtime and every historical plan are unchanged.
