# Independent event/lifetime review

Reviewed on 2026-10-11 from packet 29 ownership semantics, packet 35 native
preparation, and the installed icpx 2026.0 enqueue-functions headers. No device
binary, discovery API, accelerator file, or privileged command was run.

Findings fixed in the host adapter:

1. A retained handler cannot capture stack locals by reference. The overlay
   changes only its capture to by value and hoists launch ranges into capture
   initializers. No kernel body is rewritten.
2. The preparation placeholder event must never be marked complete in the owner.
   `Context::prepare` ignores it and requires a captured native command. The
   callback records only the real event returned at issue time.
3. Prepared queue selection must not drift with mutable `allocation_card`.
   Compute saves the card and rejects mismatch; copy saves its validated queue.
4. Deferred handlers must not retain a transient operation's `this` pointer.
   Native compilation must use `-Werror=deprecated-this-capture` so a hidden
   member capture fails rather than becoming a stale pointer. This guard caught
   the imported packet7 Stream operation's `copy` member during native compile.
   The overlay now binds that scalar explicitly as `copy=copy`; its operation
   object is not retained. Static source identity still passes.
5. No unchecked push may grow the native event vector on the hot path. Both
   prepared compute and copy callbacks reject a full capacity before enqueue.
6. The installed eventless API does not by itself preserve this owner's event
   completion protocol. Kept real events for every submission; did not substitute
   completed placeholders or silently drop profiling/failure localisation.

7. A raw Device address alone can be reused after destruction. Owner generation
   now starts from the process-unique handle sequence and refreshes from that
   sequence, so replacement owners cannot admit an old closure by address reuse.
8. Capture-order comments did not validate explicit pseudo dependencies. Capture
   now rejects zero and forward/out-of-range dependencies before binding.
9. The checked mirror and direct source can each name the same helper header at
   different filesystem paths. The overlay now adds a quoted include resolved
   by the existing mirror map, preventing duplicate helper definitions.

10. The original prepared callback still invoked a virtual bound-submission
    method. Replaced it with a preparation-only virtual factory that returns a
    concrete command-group callback. The callback owns its functor and directly
    checks sticky error/card/capacity, submits, and records the real event. Its
    backend-state pointers obey the same owner epoch and admission contract.

11. Binary identity review found the helper include prefix shifted an assertion
    source line from 45 to 48 in the packet7 module. Added `#line 1` after that
    prefix, preserving assertion payloads as well as lambda source and names.
    Final binary equality is checked in the independent kernel identity receipt.

Native compilation completed for the model, fixture, K2, and JIT entries with
`-Werror=deprecated-this-capture` after that fix. All 28 transformed command-group
bodies pass the durable transient-capture scan; all 26 ranges are prepared once.
The final native rebuild passed with the single-callback factory, latest owner/
Engine changes, and assertion-line reset. Its model binary SHA-256 is
`fe0e4ac683844d3c1143ffd6980e853e22ee7859f7cade48478d25c63ed1752e`.
No accelerator entry was executed.

Remaining device-only checks: asynchronous fault delivery under the real queue,
per-submission profiling availability, actual backend allocations, kernel-name
binary comparison and exact device output. Source review is not a device pass.
The invalidation reviewer separately audits owner and Engine generation checks.
