# One decode transaction, arithmetic identity v2

This is a design, not a captured model or a speed result. Packet20 measures only
small issuing surrogates in a future admitted window. The integrated target is
packet18 frozen parallel (2,445 physical kernels/token). One logical token
transaction may contain a graph on each of two owners and an explicit boundary
copy; it is not a claim of one native cross-device submission.

## Data changes; graph topology stays fixed within an admitted capacity

A process-owned device `TokenState` holds token ID, position, active-row count,
committed sequence length, pool count, admitted attention-slot count, expert IDs,
acceptance/commit controls and a sticky error. Allocation addresses stay stable.
The graph reads this state at execution time, never C++ captured scalar values.
The microbenchmark changes its token-state block with one H2D copy **outside**
recording, waits for that copy, then replays. Its host source stays alive through
copy completion. A production device sampler writes the next token directly;
external request state can use the same copy boundary.

| Dynamic item | Fixed-shape representation and exactness condition |
| --- | --- |
| Position and rotary lookup | Device integer index into the pinned v2 BF16 rotary table. Check bounds before any load. Same table bytes and multiplication/cast sites; advancing position changes only indices. Table exhaustion requires a separately generated/admitted table and graph rebuild if addresses change. |
| GDN, convolution and KV lengths | Stable capacity buffers plus logical lengths. Only the original valid locations are read or written. Masked work-items return before reads, arithmetic or stores. State updates occur in the original order; inactive rows cannot update history or sticky state. |
| QSA compression pool count | Fixed-capacity descriptors; current pool count is device data. Compression commits only on the original position predicate. Empty slots are excluded from selection, not represented by dummy scores. Capacity overflow sets sticky error before any write. |
| Admitted attention slots | Store ordered selected IDs and active count on device. Launch enough groups for capacity, but each head executes the exact active-prefix maximum, adjacent sum and PV trees with the original odd-tail add-zero operation. Merely padding a larger reduction with zero or minus infinity is NOT sufficient: it may change tree shape, signed zero, NaN handling or normalization. Never evaluate exp or value multiplication for an inactive lane. |
| Routed expert IDs | Device top-10 IDs in the original stable order; descending normalized score, original expert-index tie break. Descriptor lookup selects the exact packed weight bytes. Sibling row concatenation keeps each row local reduction geometry/tree. Removing gather changes only repeated input addresses to the single immutable row. No pruning, guessed routing or reassociated expert accumulation. |
| Generated token and PLE history | Sampler writes token ID with original tie rule; committed history advances only after target acceptance. Embedding and PLE host-backed tables are a current segmented-replay blocker: packet18 still reads host rows. A future stable device-addressable table or explicit H2D boundary is required. No hidden host callback is called a single replay. |
| Fixture capture | Preallocated device snapshot slots, copied from the original site only when a device predicate is true. D2H and hashing occur after replay. A capture-enabled executable has a separate identity and is not silently timed as ordinary decode. Snapshot aliasing is forbidden; turning instrumentation on can require re-recording. |

For MTP, committed and speculative state are distinct. Fixed-width verification
slots do not add model rows: inactive rows branch before every state change and
before any reduction contribution. Acceptance scan and commit retain target
verification, first-rejection order and rollback of KV/GDN/convolution/PLE/QSA
as one transaction. Packet20 does not implement or qualify MTP.

## What a graph owns

The Stage1 owner leases every allocation reachable by a graph: weights,
quantization tables, rotary constants, state, scratch, selected-ID arrays,
descriptors, token block, output and optional snapshot buffers. It also keeps
kernel bundles, executable graphs and their queues/contexts alive. Addresses
and sizes are pinned, not just wrapper objects. Weight eviction/repacking,
arena reuse or vector reallocation while a graph references the pointer is
forbidden. Graph-private runtime pools are counted in addition to the explicit
arena; the lab observed a separate reserved pool per capture unless shared.
Use one explicitly shared pool where the runtime supports and proves it; do
not infer that two graph wrappers share storage. Measure reserve and rebuild
peaks in a later memory gate. The microbenchmark explicit memory census does
not bound opaque driver/JIT allocations.

The lab also observed captured H2D reads from freed host pointers. Never record
host-pointer copies. Fill long-lived device inputs outside capture and establish
a completion dependency. A capture target does not copy results to the host,
call `.item()`, inspect a token, branch on host readback or allocate new storage.
Debug output and timing serialization are outside capture.

## Errors, boundaries and lifetime

The sticky error is cleared only at an admitted transaction boundary after the
previous transaction has drained. Within a replay all guards consult the same
slot. Cross-work-group updates use the existing atomic mechanism; the first
recorded error cannot be erased by a later kernel. Error slots alone do not
make a partially updated transaction atomic: write tentative state and commit
it only after all predicates pass, or retain a full rollback checkpoint. The
current eager path is not automatically promoted to that stronger contract.

On two cards, finish the first owner graph, perform the tracked BF16 boundary
copy, then start the second graph after copy completion. Each context retains
its own allocations and events. A borrowed native event must have a valid
cross-context transport contract; otherwise use the existing explicit host
boundary wait, honestly counting the extra submissions/waits. Never assume a
SYCL wait drains an independently created native queue. Failure on either owner
stops new work on both; it does not retry or reset a device.

Shutdown order: stop producers; bounded-poll completion on **all** owning queues;
destroy executable graphs and regular command lists while kernels, event pools
and USM still live; destroy owned native queues/events; release graph leases;
release USM through its original context; clear SYCL events and queue wrappers;
release SYCL context wrappers and finally the Stage1-owned native context.
Borrowed handles are not destroyed. A failed drain retains ownership for the
coordinator and records an incomplete teardown; a forced process exit is not
cleanup. The prepared watcher never kills or resets an unresponsive child.

## Growth and re-recording

Changing token, position or active counts within admitted capacity needs no
re-recording **if** the kernels read those values from device memory and retain
the exact logical tree. Re-record on a changed pointer, capacity, scratch size,
launch geometry, selected-slot capacity, rotary table, layer placement,
quantization dispatch, kernel identity, precision flags or fixture graph.
If the implementation specializes a reduction to active length, length changes
require a graph for that exact length; capacity masking cannot waive the tree
gate. Rebuild is outside timing, with old and new pools both budgeted until the
old graph drains. Context growth beyond the original memory admission is a new
memory gate, not a quiet reserve increase.

## Required promotion gate

Checkpoint state; run eager v2; restore; capture without host readback; restore;
replay and compare every output/state byte. Repeat with changed position,
token, each input pointer content, pool counts (including zero/odd/tail/full),
selected IDs/order, state and error conditions. Test two fresh processes.
Constant-output or unchanged-input repeat tests cannot detect inert capture.
Performance needs matched fresh owners and unchanged model gates. This packet
has no device result and cannot select a speed winner.
