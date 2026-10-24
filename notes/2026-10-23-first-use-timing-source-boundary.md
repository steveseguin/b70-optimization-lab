# First-use timing: the existing class mode changes backend configuration

Source inspection only, on the four-card host. No owner, model or device was
executed for this note; applications and settings were not changed.

The [P201 observations](../experiments/own-xpu-runtime/integration/streaming_v1/P201-PREFILL-OBSERVATIONS.md)
leave the first position's 23.511 seconds of host enqueue time unattributed.
That position scheduled zero expert-cache fill bytes. Paging, lazy runtime work
and host expert access remain hypotheses, not diagnosed causes.

The existing Engine can emit `enqueue_family_ms` with `timing=class`, but that
switch also enables native event profiling. In P198's generated `main.cpp`:

- Line 810 derives `class_timing` from `timing=="class"` and `profile_events`
  from `timing!="token"`.
- Line 1157 passes `profile_events` into the backend factory, alongside the
  existing MTP/draft conditions.
- Line 1665 accumulates host enqueue time by family only in class mode.
- Line 2208 writes a null family field outside class mode.

The inspected P198 source SHA-256 is
`1e7c5f1b6ab19f909fbd03165ead029ea7331a27810b7a6e97961d9f32039581`;
its generated path is
`experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/build/native/main.cpp`.
The [P198 overlay receipt](../experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/evidence/source-overlay.json)
records the source lineage. P214 retains the same timing coupling in its
compiled successor, whose generated source SHA-256 is
`6132a7c3cf15161647d1ec84f6af64cd091c469dbf09d0086fbfffe04de9d7f5`.
The [P214 build receipt](../experiments/own-xpu-runtime/stage2/packet214-frozen-table-publication/evidence/build-compile-only.json)
binds that source and the disabled native artifact.

The first P201 request's retained `sites.jsonl` and `progress.jsonl` are empty;
its token records have `enqueue_family_ms: null`. They cannot recover the
missing phase attribution retrospectively.

A future diagnostic that enables class timing must identify the changed
profiling configuration. To preserve token-mode backend identity, a separate
host-only first-use trace would be needed. It should record bounded phase
timings and page-fault deltas, retain normal queue ordering, and report its own
instrumentation cost. This is a later diagnostic option, not an implemented
trace, a native admission, or evidence of a performance improvement.
