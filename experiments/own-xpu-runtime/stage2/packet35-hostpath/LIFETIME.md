# Prepared submission ownership and events

Packet 35 retains packet 29's eventful compute submission and allocation
ownership protocol. Preparation does not enqueue work. It calls each selected
operation once with validated pointers. The generated host overlay intercepts
`q.submit`, saves a command-group closure by value, and binds its launch range.
The device lambda remains inside its original submit/run method. All local
accessors, including the split-one p28 accessor, remain unchanged.

The issuing path has one application indirect call: the owner invokes a callback
that owns the concrete command group and directly calls `queue::submit`. The
virtual callback factory runs once during preparation, and its temporary object
is then destroyed. The callback captures the backend event ledger, mutex, sticky
error and selected-card state by pointer; those objects must outlive the plan.
No virtual operation call survives in the per-launch path. The native backend checks its
sticky asynchronous error and the saved card before submission, reserves no new
storage, and stores the returned event in its preallocated ledger. The owner
records the same event. No event placeholder from preparation reaches either
ledger. Preparation scopes reject nesting and multiple submissions, and restore
the thread-local capture pointer even when validation throws.

A prepared closure owns its captured argument values. Pointer values borrow the
owner's allocations, and the queue pointer borrows the backend's queue. The
owner's allocation epoch and admission checks must reject replay after release,
allocation invalidation, or shutdown. Engine plan/dispatch generations must
reject stale sites before the callback. A queue switch still drains **both**
queues on the host; omission of `depends_on` only removes a predecessor already
ordered by the same in-order queue. The checked path retains layer waits and
failure localisation. One-card staging retains the legacy path.

Prepared copies use the public `queue::memcpy` shortcut after validating both
allocation extents and selecting the destination queue once. Their returned
events are tracked identically. The source and destination pointers must remain
live until the event completes; the owner capture record must include both.

## Submission forms and limits

| Form | Used | Event and failure semantics |
| --- | --- | --- |
| Prepared eventful command group, `queue::submit` | Compute | Every native event retained; completion, bounded waits, class timing, per-submission budget checks and checked layer failure attribution remain available. |
| `queue::memcpy` shortcut | Prepared copies | Same retained event and ownership as the old handler copy. |
| `submit_without_event` through experimental enqueue functions | No | icpx 2026.0 headers offer this API, but the current owner polls every recorded native event at retirement and shutdown. An eventless command cannot be substituted with a default event: that would report completion before work completed and break allocation lifetime. |
| `nd_launch` / direct kernel queue shortcut | No | Reconstructing the kernel functor outside the original handler would change its lexical kernel identity; accessors also require the handler. Device identity is prioritised over this unqualified optimisation. |

Eventless submission would require a separate segment-completion protocol with
real marker events at every card switch, checked layer, copy dependency and
shutdown boundary. It would lose individual profiling timestamps and individual
execution-budget attribution in token mode. Sticky asynchronous errors would
still need delivery/checking at those segment boundaries, and any error before
marker admission must retain all allocations. That protocol is not implemented
or claimed safe in this packet. No eventless speed claim is made.

Class timing still measures native event intervals. Token mode still cannot
measure a four-second budget for each individual kernel, matching packet 29;
the coordinator's watchdog and queue-wait deadline remain the containment limit.
The real W2 device window is required to measure SYCL runtime allocations and
submission cost. The CPU mock allocation hook covers application issue work,
not allocations performed inside the unavailable device runtime.
