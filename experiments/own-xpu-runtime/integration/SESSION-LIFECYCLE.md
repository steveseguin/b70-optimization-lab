# Bounded attached session lifecycle

## Question and identity

[session_lifecycle.py](session_lifecycle.py) supplies normal request-limit and
idle shutdown for an already admitted owner. It starts no process, changes no
host setting, sends no signal, retries nothing on the native channel, and does
not replace the outer coordinator's reservation, fault monitor or drain proof.
Native arithmetic, checkpoint contracts and existing sealed sources are unchanged.

## Outcome

Construction has an explicit order:

```python
admission = RunAdmission(
    admitted_front, guard=window_guard,
    request_limit=limit, idle_seconds=soft_idle,
    absolute_deadline=soft_absolute_deadline,
    last_native_activity=conservative_last_native_activity,
    native_idle_seconds=admitted_native_idle,
    native_absolute_deadline=admitted_native_deadline,
)
engine = CheckpointEngine(admission.front, guarded_store, **admitted_engine_options)
service = ChatService(engine, parking_for_engine, admitted_codec, **admitted_chat_options)
lifecycle = SessionLifecycle(service, admission)
server = make_server(lifecycle.service)
receipt = lifecycle.serve(server)
```

The caller constructs `Parking` against that exact engine. The lifecycle checks
that the service's engine uses the exact admission proxy and that its parking
policy uses the same engine. A front can be claimed and attached only once;
the caller must keep all other raw front/engine aliases unused. This is an
exclusive borrowing contract within trusted coordinator code, not isolation
against hostile Python callers.

`serve` accepts only this project's serial HTTPServer, polls accept for at most
250ms, and evaluates ordinary close conditions between complete handlers.
`request_close()` is a thread-safe latch. It never concurrently closes a front.
An admitted request finishes its normal SAVE/RELEASE before the loop closes
intake, closes the listener and calls `NativeFront.close()` once. A successful
receipt requires a verified stopped event, matching counters, no discarded
pending reply and process exit zero. The outer coordinator must still prove
physical device drain before releasing its lease.

## What worked

Sixteen CPU tests use actual loopback sockets, the real chat facade, checkpoint
adapter and parking policy, with explicitly synthetic native replies/state.
They cover idle and request-limit close, a close latch during a turn, incomplete
work before RUN, native idle already queued, native-exit races, guard failure,
exclusive attachment, incorrect terminal proof, and private exception retention.

The proxy invokes the supplied guard immediately before RUN, then rechecks
local deadlines, count, ready/pending state and process liveness immediately
before forwarding. RUN and SAVE/RELEASE also receive post-operation guards.
SAVE/RELEASE guards do not enforce a newly requested soft close: the admitted
turn is allowed to finish its disposition. Failures remain incidents.

Initial activity is supplied explicitly by the coordinator. Proxy construction
never resets it. Following SAVE/RELEASE, the module records the timestamp from
**before** control dispatch, conservatively earlier than the native reader's
next idle period. Health checks and malformed/unsupported requests never refresh
native activity. Local idle/absolute limits cannot exceed the independently
admitted native limits; readiness alone does not attest startup timer arguments.

## What failed or remains uncertain

If a close/expiry is observed before entering the real service, no adapter
operation starts and normal close is permitted. If a deadline expires during
codec/policy work and the immediate pre-RUN guard refuses, the adapter has
already entered an operation: this is an incident. It returns no clean receipt
and does not automatically close, release or signal the retained owner.

The native reader can independently expire between any liveness check and RUN.
The module does not claim to remove that race: an actual protocol failure keeps
its original exception, halts intake and receives no retry. Exceptions swallowed
by HTTP's generic503 are captured at the service boundary; serialization is
preflighted there to retain its actual error. An unexplained HTTP halt or an
already-poisoned adapter also fails closed. Listener cleanup errors are secondary
notes and do not replace the captured runtime failure.

The caller remains responsible for guarded metadata snapshot/delete operations,
continuous device/fault monitoring while handlers run, conservative native timing
provenance, filesystem/RAM admission and incident handling. No launcher, package,
restart recovery, indefinite service, multi-user isolation or device qualification
is introduced. Session and parking indexes remain process-local.

The initial 12-test candidate lacked explicit handling for an HTTP-internal halt
and externally poisoned service state. Its exact source/tests/log and review
findings are retained under
`lineage/session-lifecycle-before-transport-halt-review/`; the current tests cover
both gaps.

## Evidence and patches

See [tests](test_session_lifecycle.py),
[CPU receipt](receipts/session-lifecycle-cpu-20261023.json),
[test log](receipts/session-lifecycle-cpu-20261023.log), and
[independent review](receipts/independent-session-lifecycle-review.json).

```bash
nice -n19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_session_lifecycle.py -v
```

## When to revisit

The separate host-only proof below validates actual soft-limit QUIT and counters.
Native idle expiry remains covered by CPU race tests rather than that two-turn
run. A later real-device coordinator must bind this additive module and
its admitted timers into new readiness evidence. Keep the existing benchmark
package and frozen p199 worker intact; this CPU module is not a live endpoint.

## Actual HOST_ONLY proof, 2026-10-23

The [separate probe](session_lifecycle_host_probe.py) passed once through the
unchanged GNU HOST_ONLY binary, actual protocol-v2 front, native store, adapter,
parking policy, ChatService, loopback HTTP and this lifecycle. Two synthetic
requests generated eight tokens and saved two checkpoints. The lifecycle's soft
two-request bound then sent QUIT before the native eight-request limit. The
stopped receipt reports two requests, two controls, no discarded pending reply
and exit zero. There was one close call and no incident signal.

The [independent result audit](receipts/independent-session-lifecycle-host-result.json)
checked actual HTTP mapping, both input/output streams and all 42 small state
binary files. The complete useful run is copied under
[session-lifecycle-host-a](receipts/session-lifecycle-host-a/copy-inventory.json):
89 files, 819,912 bytes; only two empty lock files are omitted. This fixture uses
context64/vocab16 and an explicit synthetic alphabet codec, not production text
or model arithmetic. It performs no GPU operation or real-model qualification.

Six preparation tests also pass after the run. They use fresh UUID scratch
bindings without creating a directory or executing native code, so the preserved
actual output cannot make future test runs fail. The exact test bytes used for
preparation and the real run remain under
`lineage/session-lifecycle-host-tests-before-run-closeout/`; the real-run plan
retains their original hash. A prelaunch HTTP error race was fixed and its prior
source/plan evidence retained under
`lineage/session-lifecycle-host-before-http-error-review/`.
