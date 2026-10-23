# Bounded attached serving composition

## Question and identity

Can the experimental p198 owner serve a bounded interactive local session using
one already admitted model process, the existing full BF16 checkpoint format,
and the tested chat/parking components? `bounded_serving_session.py` composes
those pieces. It has no launch command or service installer.

The production entry point is `attach(profile, front=..., store=...,
admitted_argv=..., launched_at=..., last_native_activity=..., guard=...)`.
The independently built `bounded_serving_profile.py` profile pins the source,
binary, model, codec and exact argv. Production attachment accepts the exact
NativeFront and NativeCheckpointStore classes, checks their roots and counters,
rehashes the store's held ELF, compares held/current directory identities, and
checks loaded module origins. It never learns trusted identity from a checkpoint.

## Outcome

Nineteen CPU tests pass. Twelve component tests cover actual loopback sockets,
the engine adapter, parking policy, chat facade and lifecycle with synthetic
native components, including receipt exclusion during service. Seven test public
attachment boundaries with the profile validator explicitly mocked only there. Production profile validation has no mock or
synthetic-mode switch. No native owner was started for this composition proof.

After attachment, call `open_listener(('127.0.0.1', 0))`, then `serve()` in the
coordinator's chosen thread. `request_close()` only latches normal closure.
`receipt()` is available before serving and after success or incident; it refuses
while serving or closing rather than reading mutable policy state concurrently.
The returned receipt is a mapping; the coordinator owns durable bounded writing.

## What worked

The profile fixes 16 requests, context4096, max512 new tokens, 512MiB parking and
a 256MiB per-SAVE reservation. The same admission proxy guards RUN and
SAVE/RELEASE; an exclusive store wrapper guards metadata snapshots and deletes
before and after each operation. One Parking instance holds all session state.
A normal count/idle/close boundary stops HTTP intake, completes any admitted
reply's disposition and sends one graceful QUIT through SessionLifecycle.

Malformed client input does not reach RUN. Runtime, metadata and fault-guard
failures retain the original exception, halt intake, preserve ambiguous state,
and leave the owner and store with the outer coordinator. Attachment or runtime
failure does not close, restart, signal or retry the owner. Repeated `serve()`
refuses without destroying a previously successful terminal receipt.

## What failed or remains uncertain

An initial test invocation used the wrong working directory and did not create
or execute the intended test module. The first public-attachment fixture lacked
the executable mode/ELF header required by NativeCheckpointStore and failed
before any execution. Exact failed sources/logs and passing pre-review versions
are retained under `lineage/bounded-serving-*`.

This component supplies no physical device admission, leases, fault monitor,
owner startup, stderr drainer, cache quota, storage cleanup or endpoint restore.
The profile remains `live_admission_ready=false`: 768MiB is a proposed write
forecast, not a certified bound on every native/driver writer. The coordinator
must resolve that budget and independently monitor space and faults during work.
Raw owner/store aliases are exclusively borrowed by agreement with the trusted
coordinator; this is not a security boundary against malicious Python callers.

Soft idle240 and absolute4800 seconds remain below native300/7200 seconds.
`launched_at` is sampled before launch; `last_native_activity` is a conservative
coordinator observation. Neither proxy construction nor a received readiness
event resets the clock. Using launch as activity includes model loading: a
215-second load leaves25 seconds of soft idle. A later origin requires separate
timing evidence. Native expiry can still win after the immediate pre-RUN check;
that protocol error is an incident, with no retry or fabricated clean shutdown.

## Evidence and patches

- [Composition source](bounded_serving_session.py)
- [CPU socket and attachment tests](test_bounded_serving_session.py)
- [CPU receipt](receipts/bounded-serving-session-cpu.json)
- [Lifecycle contract](SESSION-LIFECYCLE.md)
- [Storage audit](receipts/bounded-serving-storage-budget.json)

The existing p197/p198/p199 sealed sources and binaries are unchanged.
The synthetic private `_compose` test seam does not validate a production
profile and is not a supported coordinator entry point.

## When to revisit

Before a live bounded session, complete the independently reviewed coordinator
admission and storage design, preserve launch timing and argv provenance, and
review the exact composed profile. No live qualification or performance claim
follows from these CPU tests.
