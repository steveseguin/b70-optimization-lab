# Independent lifetime review

Source review only, 2026-10-11. No device discovery, device execution, or GPU
library call was performed. Initial review covers packet18 `LIFETIME.md`,
packet22 `review-lifetime.md`, `recording_native.hpp`, `recording_native.cpp`,
`recording.hpp`, and Stage-1 packet3-prep `owner.hpp`, `owner.cpp`, and
`sycl_device.cpp`. This review did not author the recorder implementation.

## Ownership required for this benchmark

The Stage-1 Device remains the sole owner of its native context, queue and
arena. A graph recorder borrows that queue; it must never create a second
context or release the borrowed context/device. Each captured pointer must
resolve to an allocation whose address, size, identity and generation remain
stable through the recorder's successful clear. Both the arena and host state
comparison buffers remain alive through all completed readbacks.

All 24 layer recordings must share the admitted device allocations. Separate
recordings may still reserve opaque runtime memory: shared explicit buffers do
not prove bounded opaque memory. Account second/third captures independently.

Concrete commands and binding arrays must be copied by value. A lambda retaining
a stack operation, span, command-group handler, or temporary binding vector is
invalid even if its first immediate submission succeeds. Returned SYCL event
objects and executable kernel bundles retain context resources too.

## Required destruction order

1. Close submission admission and persist the result or failure receipt.
2. Prove completion of every submitted operation with one bounded drain budget.
3. End an active capture where safe; destroy executable and modifiable graphs
   (or raw command lists) while allocations, kernel wrappers and owner queue are
   alive. Clear each recorder before destroying it.
4. Drop recorder execution-event wrappers, native kernel wrappers, recorder
   objects, and the shared card-recording object. Raw implementations must also
   destroy recorder-owned completion events/pools/queues. Borrowed handles stay
   with the owner.
5. Drop all application-held SYCL event and bundle objects, then release arena
   allocations through owner shutdown. The owner's final idle marker completes
   before it clears its event map and releases queue, SYCL context, then native
   context.

Place resources in an inner scope beneath the Device lifetime. The error handler
must run inside that scope; ordinary exception unwinding is unsafe when a graph
is ready or a submission may still be in flight. Packet22 deliberately retains
the child in those cases instead of destructing resources.

## Error paths to gate

- `begin()` may allocate a graph and throw before setting `active`. `clear()`
  must still dispose of that partial graph before owner teardown if no work was
  submitted; do not rely only on `recording()` to decide whether cleanup is due.
- Capture submission or `finalize()` may fail while a modifiable graph remains.
  Write the error first; clear the capture without executing it, unless native
  ownership or queue state is uncertain.
- Packet22 sets `in_flight` before graph submission and resets the old completed
  event. A failed enqueue therefore has no stale completion proof. Preserve this
  behavior. An absent completion event after possible submission requires the
  process and all ownership to be retained for the coordinator.
- A failed clear or a failed native destruction must not be retried in catch,
  shutdown or a destructor. Save a refusal receipt and retain the child.
- Stop after a comparison mismatch; do not launch the next replay mode. A
  completed mismatch can use normal safe teardown after writing its evidence.
- Fault/time-budget expiry must not hard-kill, reset, exit through live resource
  destructors, or trigger another recording. The wrapper retains a busy child.
- CPU lifetime gates must cover partial construction, capture exception,
  finalize exception, old-event replacement, failed enqueue, failed drain,
  failure during clear, normal clear of multiple recordings and destruction of
  the last event/bundle before context release.

## Review status

The existing packet22 native backend meets the explicit resource ordering when
its `clear()` contract is honored. Its retain-on-failure destructor is deliberate
and cannot replace writing a failure receipt at the benchmark call site. A
benchmark implementation review and CPU gate receipt remain pending below.
A CPU test cannot establish driver pool behavior, successful capture of current
kernel classes, or clean physical device teardown.

## Packet34 backend follow-up

Independently reviewed `backend34.hpp` after implementation. It uses its own
single owner context and one in-order profiling queue. It preserves original
operation submission bodies, keeps captured SYCL events distinct from execution
events, and retains executable/modifiable graphs beneath that owner. Direct
submission or graph enqueue sets the uncertain flag before entering the runtime;
failed submission can never use an older completed event as completion proof.
The 24 graph variant intentionally enqueues several graphs without an intervening
wait; completion of its last event proves earlier work complete on this in-order
queue. Only graph capture events are treated as completed topology.

Two findings were fixed by this reviewer and disclosed as authored fixes:

- `clear_recordings()` now checks every non-capture event for completion and
  requires an empty owner queue before deleting graphs or event wrappers.
  A caller cannot accidentally release graph leases while eager work is pending.
- Native allocation now rolls back the allocated pointer if insertion into its
  host allocation registry throws. A failed rollback retains the owner.

Capture begins only on an idle queue. Allocation, device-address replacement
and frees are forbidden with retained graphs; host/device copies are forbidden
inside capture and while replay is pending. Finalized graph/source pairs clear
before allocation teardown. Constructor failures release queue, SYCL context,
then native context; normal close checks that no queue borrowers survive. A
partial begin may require attempted end_recording during clear; if that fails,
the caller must retain the owner rather than retry.

The new window supervisor was authored by this reviewer and is not claimed as
independently certified. Its standard-library fake-child suite passed 13 tests,
including interrupted/faulted/journal-failed/watchdog-limited children retained
without hard kill, failure persisted before cooperative stop, and K0 retained
without a signal because the unchanged JIT program has no graceful handler.
The suite runs serially and launches no child or device program. Its receipt is
`window-tests.json`. Final benchmark-call-site exception/teardown review remains
pending until that source is available.

## Final benchmark call-site review

Reviewed `bench.cpp` and independently inspected `fixture34.hpp`. Fixture
snapshots and concrete mock command objects contain host values only; they hold
no queue, event, bundle or native context object. Native owner/graph resources
stay in the heap-owned Engine across the exception handler. Captures and replays
retain stable arena buffers, and successful runs clear graphs before owner
shutdown. Capture failures and comparison failures write `failure.json` before
attempting bounded cleanup. Uncertain enqueue and asynchronous errors refuse
the drain/clear path and retain the owner.

One additional finding was fixed by this reviewer: a normal-path clear or
shutdown failure could enter the exception handler and attempt cleanup again.
An outer teardown-attempt latch now records the first attempt. Any exception
after that point retains ownership immediately instead of calling clear or
shutdown twice. This applies to the host census path as well.

Generator review found no scale-layout defect. The generated Q6_K scale uses
byte offset 208; IQ2_S, IQ3_XXS, IQ4_NL and Q8_0 scales use offset zero. Finite
small half scales replace the unconstrained random bytes; integer fields accept
all generated bit patterns. CPU generation gates decode all 32 repeating blocks
and reject nonfinite values. Scalar F32/BF16 values are bounded and norm tensors
have a positive offset. This is a synthetic valid-data workload, with no claim
that random values represent model quality.

The separate `lifetime_test.cpp` model injects partial begin, finalize, enqueue,
drain and clear failures. It explicitly counts context borrowers, rejects
release under leases, checks shared-recording leases, verifies command value
cloning, and rejects escaped event/kernel wrappers at context close. This model
is independent from SYCL and does not prove runtime-internal destruction order.
The serial runner builds with g++ and Intel icpx, with and without ASan/UBSan,
and uses two fresh processes per variant. Its receipt is `lifetime-tests.json`
when run; all temporary binaries are removed. Native clean exit, capture memory,
and current-kernel capture support remain K0/R1 device-window gates.

The lifetime model gate completed: **8 fresh processes, 304 checks**, all passing
(g++ and Intel 2026 icpx; plain and ASan/UBSan; two processes each). Hashes and
precision flags are retained in `lifetime-tests.json`; temporary model binaries
were deleted. No model-device binary, SYCL API or Level Zero API was executed.

A final exception-path check found that recorder clear erased backend event IDs
while the owner's integer event ledger could still refer to captured commands.
The subsequent owner drain would reject those IDs. Clear now drops captured
SYCL event wrappers but retains their synthetic completed ledger entries until
owner retirement/shutdown clears both ledgers. Completed eager events remain
owned too. This repair preserves graceful cleanup after abandoned capture and
does not execute the discarded graph.

The optional `driver_memory()` counter was also reviewed: it queries the already
owned queue's device only, creates no context and performs no discovery. It
checks the fault latch first. Missing free-memory support, feature-not-supported
or invalid-query errors produce explicit unavailable accounting; all other
errors propagate. Its local device wrapper is gone before owner context release.
The capture-ledger and optional-counter revisions are source-reviewed; only the
coordinator window can check their native behavior.

The final wrapper revision adds a process-tree RssAnon sensor using only `/proc`
reads, a 7.5 GiB stop threshold below the 8 GiB bound, and summary validation/hash
binding before R1 success. The serial fake-child suite now passes **18 tests**,
including JIT-thread descendants, duplicate child references, missing live root,
unavailable memory sensor, memory-triggered retention and summary refusal.
Temporary test trees were deleted. Expected duration is now 300 seconds and
both coordinator commands use the 1,200-second watchdog.
