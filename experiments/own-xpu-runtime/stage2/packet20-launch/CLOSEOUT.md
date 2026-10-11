# Packet20 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Question: can issuing fewer host commands and fusing consecutive v2 sites cut
per-token launch overhead by 5–10× while retaining every result bit?
Identity: packet18 frozen parallel, `iq3-p17-detmath-v2`; GNU and IntelLLVM
2026.0 host gates; native precise divide/sqrt and no-contraction flags on both
compile and link. This is our own packet, using Intel platform APIs as
dependencies. No external inference runtime source was adopted.

## Outcome

Outcome: prepared a tiny one-card launch-method comparison; all nine methods,
raw SPIR-V and dynamic-parameter API compile/link. The output matrix and
fault/loader/latch supervisor have CPU-only mocks. Copied v2 non-GEMV kernels
have exact host fixture comparisons with two compilers and fresh repeats.
No device ran, no model speed was measured and no production method was chosen.

## What worked

Useful mechanisms retained: explicit event versus implicit/discard event
controls; graph/native-list replay with changing device-resident state;
first/last timestamps where available; eight-operation same-work baseline;
whole-phase barriers for legal fusion; exact probability ranking across
work-groups; single-row expert input ABI; device-state replay design and pinning.

Review fixes retained: lifetime holds before destruction on a failed drain,
long-lived H2D sources, mutex-protected asynchronous error, native queue drain
independent of SYCL queue drain, changed-input output verification, exact odd
tail reduction behavior, invalid attention-ID prevalidation, packet18 site
normalization and physical GEMV pass accounting. See the
[independent review](review/INDEPENDENT-REVIEW.md).

## What failed or remains uncertain

Limits: global fusion is a correctness prototype and may serialize too much.
The rule(ii) GEMV interfaces are designed, not implemented. CPU parity is not
device parity or full-model equality. Raw/graph API availability at compile
time does not establish B70 runtime support. Opaque runtime memory and blocking
driver calls prevent certifying a total <64 MB footprint or hard <60 s elapsed
time before measurement. Explicit device buffers are 87,040 bytes; work has a
600 s child watchdog (300..1800 s) and five-second completion polls. The host
halt remains binding; no recovery or device launch was attempted.

## Evidence and patches

Evidence retained: [build receipt](build-receipt.json),
[fusion gate](fusion/build-receipt.json), [DAG and counts](fusion/README.md),
[issuing build](issuing/build-receipt.json),
[CPU harness tests](evidence/window-tests.txt), [replay design](REPLAY.md) and
[exact prepared window](WINDOW.md). Disposable scratch is deleted; ignored
compiled artifacts remain to make the prepared command concrete.

## When to revisit

Revisit: after separately authorized host recovery, run the one-card window,
then a separately admitted fresh owner for any speed verdict. Select issuing
method only from exact changed-input results. Integrate useful fusions with
packet18 layer/state fixtures, then test eager/replay and two fresh processes
before a model performance claim. No scoreboard entry or public result is made.

## October 11: watchdog correction, CPU only

Closed arm: **a watchdog set to the expected run time**. The old 50 s native
admission and watcher cutoff are removed. Startup/JIT/setup and device envelopes
are reported separately; <60 s is a reporting goal, never a signal or pass gate.
The watchdog defaults to 600 s, refuses below 300 s, and allows at most 1800 s.
The watcher retains a still-running child after 60 s of cooperative drain.
[Every deadline and its margin](../packet18-decode-v2/DEADLINES.md).

The issuing binary was rebuilt without execution; 27 CPU wrapper tests passed.
GNU/Intel fusion oracle gates and fresh-repeat receipts were reused because none
of their bound sources, fixtures, compiler commands or binaries changed. The
seal rechecks those identities and records the reused receipts. No long CPU
oracle gate was rerun. No device ran; PID 183867 and host FAULT HALT are untouched.
