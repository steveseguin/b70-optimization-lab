# Packet 34 recorder lifetime

Packet34 follows packet18's context-lifetime repair and packet22's retain-on-fault
contract. Its native backend owns exactly one native context, one SYCL context
wrapper and one in-order queue. The graph source and executable belong to that
backend; command closures use the runtime's existing submission bodies. Raw
Level Zero replay is blocked and creates no additional native queue or list.

All device buffers are allocated before capture. No allocation, address change,
release, host callback, upload or readback is allowed inside a recording. Every
recording uses the same live arena. While any graph exists, the backend refuses
allocation and release, which prevents both address reuse and stale allocation
generations. The three whole-half captures and three sets of layer captures keep
that admission until all recordings are cleared. Snapshot vectors and the mock
recorder's value-cloned commands hold host data only.

The owner validates its integer dependency IDs. As in packet29's resident
same-card backend, actual native operations rely on the in-order queue and pass
empty SYCL dependency vectors. Layer graphs are submitted in that same order;
the last completion event proves completion of their predecessors. Control
uploads and complete-state readbacks stay outside capture and finish before the
next timed submission. They do not create graph dependencies on host pointers.

Successful teardown follows this order:

1. Stop admitting benchmark work and prove all queued work complete.
2. Clear the replay completion wrapper and captured event wrappers. Preserve
   synthetic completed integer IDs until owner event retirement, so abandoned
   capture cannot leave the owner referencing erased IDs.
3. Destroy each executable graph, then its modifiable source, while the queue,
   context and arena allocations remain alive. Release all recordings.
4. Run owner shutdown: drain owned events, release arena allocations, complete
   the final idle marker, clear remaining event wrappers and IDs, destroy queue,
   destroy SYCL context wrapper, then release the native context.

The backend checks that no eager work is pending before graph destruction, and
rejects queue release while any graph, allocation, event or replay remains.
No application event, bundle or borrowed native handle survives the owner's
context. The optional memory-query device wrapper is local to the query.

Every native submission marks ownership uncertain before entering the runtime.
It becomes certain only after the returned event is stored. In particular,
graph replay clears its old completed event first: a failed new enqueue cannot
reuse stale completion as proof. Uncertain submission, asynchronous error or
failed draining retains the complete owner for the coordinator.

Capture/finalize or byte-comparison failures write `failure.json` before the
first cleanup attempt. A partial capture may be ended and discarded without
execution when its queue is known idle. A teardown-attempt latch prevents
catch handlers or owner destructors from retrying a failed clear or shutdown.
A failed teardown writes `retained-owner.json` and retains the process; no hard
kill, driver reset, forced native release or automatic restart is used.

Memory records include fixed arena allocation bytes, graph-reported required
bytes and host RSS before/after each recording. The optional installed Intel
free-memory counter queries only the owner's device. Unsupported queries report
unavailable; other errors stop the window. A fault-latch check precedes the
query. Graph-reported bytes above 1 GiB fail admission. When the driver counter is
available, each new recording requires at least 2 GiB free, and cumulative
free-memory loss above 1 GiB stops recording. Opaque driver allocation
and complete cleanup remain unproven until the coordinator executes K0/R1.

`review-lifetime.md` records the independent review and disclosed fixes.
`lifetime-tests.json` covers an independent CPU ownership model: 8 fresh processes
and 304 checks across g++/icpx, plain/ASan/UBSan. It models partial construction,
failed finalize/enqueue/drain/destruction, shared leases and escaped event/kernel
wrappers. The benchmark's own sanitizer gate separately exercises its actual
host mock recorder, workload and byte comparisons. Neither CPU sanitizer can
validate SYCL/driver internals or physical device teardown.
