# Context lifetime repair, 2026-10-11

W0 completed its device work but aborted after saving its passing native receipt.
The last executable bundle reference in `run_canary` survived owner shutdown;
SYCL/UR pool destruction then used the already released Level Zero context.
[Original evidence](evidence/20261011-w0-a-exit-abort/README.md) remains intact.

## Lifetime inventory

| Object / holder | Destruction relative to native context release |
| --- | --- |
| W0 executable kernel bundle, returned by `tp2::Context::canary_bundle` | Inner work scope ends before explicit `d.shutdown()`. Device is declared outside/before that scope, so exceptions also destroy the bundle before owner destructor shutdown. |
| W0 `CopyEngine`, work/drain/increment/peer/verify/special lambdas | Same inner scope. They hold owner references, pointers, allocation/event IDs; none own a SYCL object. `select` holds only a raw backend pointer. |
| Two-card `tp2::Context::events` (`sycl::event`) | Completed segments retire through synchronize/clear_events; final shutdown clears remaining events after its idle marker and before either queue. |
| Two-card `queues[0/1]` (`unique_ptr<sycl::queue>`) | `close_queue()` destroys both, after events and allocation release, before `close_context()`. |
| Two-card `context` (`unique_ptr<sycl::context>`) | `close_context()` resets it before `zeContextDestroy(native)`. Constructor failure uses the same queue/context/native order. |
| Local dependency vectors and submit-return events | Temporary vectors and returned events die inside copy/compute/marker calls or are transferred to the backend event map. No SYCL event escapes to Engine; public events are integer handles. |
| Engine `peer_context` and forwarding backend `Forward::p` | These shared pointers can outlive shutdown, but refer to an emptied backend: event map empty, both queues null, context null, native null. Their destructors destroy no SYCL object. Device is a single owner of the shared two-card backend. |
| Engine pending launches, peer bridge, snapshots and fixture `step` capture | Pending launches contain integer event handles. Peer copies use the backend above. Snapshots/slots store allocation handles; fixture capture stores host byte vectors and captures Engine by reference. No context-retaining SYCL object is held. |
| Adapter, parallel/core operations, GEMV operations in packets 2/6/7/8/9/10 | Operation structs contain scalar descriptors, IDs and pointers. `submit` borrows queue/dependencies, submits command-group lambdas synchronously, and returns an event into the backend map. Local accessors/nd_items/atomic_refs are command-group/device objects; completed work and queues are drained before release. |
| Kernel objects / cached executable bundles in decode | None are retained by repository code. Search of every compiled C++ dependency finds the W0 bundle only. Packet7/8 `capture(queue)` caches a JSON string of device properties, not the queue, device, kernel or context. Static maps/counters/registries contain CPU values. Driver/runtime-internal caches still require the fresh device exit check. |
| One-card `SyclDevice` | Same event/queue/context/native sequence; source unchanged. Async handlers retain `this`, not SYCL objects, and queues/context release while their backend remains alive. |
| Owner graph destruction callbacks | No graphs are registered by this decode path. Owner's generic shutdown destroys graph callbacks before allocations/events/queues/context. |

No Engine, adapter, owner, peer backend, GEMV or arithmetic implementation was
changed. `main.cpp` changes only the host-only mock include/base/copy qualification.
The new mock models one shared context, two queue wrappers, every event and the
canary's bundle. It records destruction order, rejects native release with live
borrowers, and aborts on late destruction. Both one/two-card mini decode and W0
run through it; six deliberate late-object controls and exception unwinding are
checked separately. This proves the modeled ownership protocol, not driver internals.
The dependency sanitizer retains its separate mock; its staged canary replaces
the bundle with a scalar for compilation only. Its mini/integration decode
checks are rerun, and its original real-model binary/manifest remain preserved.

## Receipts and reuse

`repair_build.py` runs only cheap host checks and compile-only device builds.
`lifetime-reuse.json` hashes every earlier model input, reconstructs the three
host-only main edits and the added CMake test target, then verifies the previous
watchdog repair's explicit reversible edits against the original long-gate
source hashes. Canary changes are isolated from decode by the existing CLI
branch. All reused real-model receipts keep their original binary identity.
No arithmetic or launch-order exception is needed: those sources and the entire
Engine body are byte-identical. The coordinator must rerun W1 against the oracle
on the new binary before W2/W3. Neither a source proof nor a CPU mock establishes
a clean two-card device exit.

The wrapper remains failed on a nonzero native exit, even if its complete native
receipt passed. It now saves `exit_status: "device work passed; exit abnormal"`,
`native_work_passed: true`, the native receipt and hash. Kernel-fault/watchdog
reasons and the boot latch remain intact; classification does not authorize retry.
