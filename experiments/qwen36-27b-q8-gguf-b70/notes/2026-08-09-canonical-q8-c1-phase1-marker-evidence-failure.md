# Canonical Q8 Phase-1 marker-evidence failure

Date: 2026-08-09

## Classification

The corrected four-card Phase-1 run completed all four sequential oracle
captures, then failed closed at the lane-attestation gate. This is a
harness-evidence failure, not a promoted model result. The captured oracles are
useful diagnostics, but they must not be used as selector handoffs until a new
passing Phase-1 packet reproduces them with the complete lifecycle evidence.

Failed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260809T233415.924819947Z`

The packet is hash-sealed, intact, and exhaustive. Verification from inside the
run directory passed for every entry in `wave-artifacts.sha256`.

- artifact-manifest SHA-256:
  `e02d94195ba30ce4abf0b733b3c29388b4728d5d4b8a7071dd893d0a062d2935`
- detached failure-marker SHA-256:
  `79efa751e87810c56e897d9d7fcfd221bb6fa141b9ff7fcce7a72861100255fd`
- marker classification: `diagnostic-only-failure`, `evidence_valid=false`,
  `performance_promotable=false`

## What completed correctly

All four fresh c65536/np2/non-unified-KV servers reached the synchronized
barrier. GPU 0 and GPU 1 used selector 0; GPU 2 and GPU 3 used selector 1. Each
lane completed the forward sequential slot-0/slot-1 capture, both live process
bindings, runtime final verification, and orderly server teardown.

Offline validation of the sealed files found that every oracle passes the full
sequential-oracle schema and correctness gates. The two 512-token arrays,
content hashes, stream/replay arrays, semantic rows, and canaries match the
fixed sequential adapter on all four cards. Selector-on and selector-off rows
also match each other exactly. These are diagnostic correctness observations
only: the failed lifecycle attestation prevents promotion or Phase-2 handoff.

## Why the evidence gate failed

All four lane attestations failed only `selector_markers`:

- the authoritative launcher identity records the exact selector on every
  lane, but the optional backend startup line was absent from server stdout;
- selector-off lanes emitted no canonical route markers;
- selector-on lanes each emitted the exact flat first-hit before release and
  no recurrent or violation marker;
- selector-on lanes did not retain a final counter summary after TERM.

The counter summary is emitted while the SYCL backend is destroyed late in
server teardown. The common logger is asynchronous and the server returns
without a final common-log flush, so that late line can be lost even though the
server begins orderly cleanup. A first-hit proves that a route was reached but
cannot reconstruct process totals. The failed packet therefore cannot support
replicated selector-on counter evidence or any request-time dispatch claim.

A second harness defect masked the initiating lane-attestation failure in each
child log: the EXIT trap ran after `child_main` locals had unwound and then
referenced the local `server_pid`, producing an unbound-variable error. The
outer packet still failed and sealed correctly. Its cleanup record reports no
forced kill or survivor, and the retained post-cleanup session, listener,
relevant-process, and passive device-fault evidence is clean.

## Harness-only remedy

The next attempt keeps the runtime bytes unchanged and uses the server's
default-disabled idle-unload mechanism as an observable destruction boundary:

- Phase 1 opts into an exact 60-second idle interval, recorded in launcher,
  attester, oracle, and live argv identity;
- a bounded non-inference `/metrics` keeper prevents a ready lane from sleeping
  before the barrier, then is stopped and reaped before the byte-exact
  preclient boundary and timed capture so it cannot perturb measurement tasks;
- only the intended oracle-capture HTTP requests follow the preclient boundary;
  there is no keeper or other background HTTP after it, and no HTTP at all
  after the postcapture boundary or intentional sleep transition;
- the runner requires exactly one queue sleep entry followed by one server
  sleep entry while the same PID, start ticks, argv, and listener remain live;
- selector-on requires its real process-total summary after server sleep;
  selector-off continues to require zero canonical route markers;
- any early sleep, wake/reload, duplicate marker, missing summary, PID drift, or
  bounded-wait expiry fails closed;
- EXIT cleanup state is initialized outside the function-local frame, and an
  executable regression forces a post-attestation failure to prove the original
  status/cause is retained and the failure packet seals without nounset masking.

The sleep interval is part of the model-study server identity, not a Phase-1
only accommodation. The Phase-2 crossover must also pin exactly 60 seconds,
keep each ready server awake until its release boundary, stop and reap the
keeper before measured capture, and retain the same postcapture idle-unload
and summary lifecycle evidence. The matrix consumer continues to require exact
equality between the sealed oracle identity and the live Phase-2 attestation;
a sleep-disabled Phase-2 server is therefore an intentional hard failure, not
an identity-normalization case.

Selector-on counters from this diagnostic are explicitly process totals and may
include startup warmup. The study makes no request-time attribution or
performance claim.
