# Token-data review

Reviewer: separate Codex review agent. The upstream source review was read-only.
This agent subsequently implemented the synthetic fixture helper; review of that
helper is not independent. No device ran.

## Upstream findings

Packet29 main.cpp Engine::prepare_plan prepares the resident two-card path once.
Engine::linear calls selected packet28 submission entry points and R5 expert-down
code. A one-card benchmark must use those entry points with resident full expert
banks. The existing a.cards == 1 engine path instead stages layers, host-reads
router IDs, evicts expert weights and uploads selected banks.

Packet29 owner.cpp Device::compute appends the preceding logical event handle
to its dependency span. The resident TP2 backend.hpp dependencies function
validates that every handle belongs to the target card, then returns an EMPTY
SYCL event vector. The actual device dependency is therefore the in-order queue,
without explicit same-card SYCL fences. Submitters call handler.depends_on with
that empty vector. Packet34 faithfully retains owner-handle validation and
in-order queue execution. This corrects the initial review based only on the
owner and submitter layers; the backend was subsequently traced as well.

Token-dependent values already held on the device:

- Position is the canonical position allocation. adapter.cpp Bound loads it
  through a pointer. Glue mode 1 copies it into the parallel control buffer on
  the device. QSA uses that value for RoPE, append position and valid-ID bounds.
- Router outputs and route descriptors live in device allocations. Paired
  gate/up and expert down consume those allocations. Captured expert count
  and top-k count are fixed extents, not the selected IDs.
- Attention capacity/budget are fixed allocation and launch bounds. The active
  count comes from sentinel-terminated device IDs and device position.
  specialised.hpp attention_count and packet18 attention both consume these
  values from memory.
- Active/error controls are pointers. Any host-uploaded test control must
  affect these real buffers rather than an unused diagnostic allocation.

Packet29 has no dynamic ping-pong selector in its kernel argument structures.
Prepared Matrix/Spec bindings contain fixed pointers. Packet34 must therefore
provide a consuming boundary operation or separate parity recordings. Uploading
a parity number that no kernel consumes proves nothing. A device-selected
boundary copy can preserve unchanged compute kernels; its extra launch must be
disclosed separately.

## Workload scope

Layers 24–47 avoid the unique layer 1 PLE path and contain18 GDN and 6 QSA layers.
The original packet29 plan fuses the final layer 47 combine with final.norm.
Preserving that output and norm weight retains the actual kernel class without
adding a separate launch. The final head, logits and argmax remain excluded.

Four canonical layer weight sets24–27 map by24 + (layer % 4). The complete admitted
metadata shows no shape, format or extent conflict for these aliases. Synthetic
values depend on the canonical tensor name. Per-layer recurrent and attention
state must not share these weight aliases.

## Required acceptance checks

Captured values may be addresses, immutable shape/format/dispatch metadata,
launch geometry and value-cloned operations. Iteration, position, expert ID,
attention active count and parity may not be captured scalar arguments.

The variation gate must inspect actual route IDs and attention slot counts.
Changing intended inputs is insufficient without demonstrating changed outputs.
At least two expert selections, multiple attention counts and both parities
must be consumed by the real workload.

Store and compare every iteration byte-for-byte, including recurrent state, KV
state, pooled state, route outputs, streams, position, controls and parity-visible
buffers. Restore identical initial state for each mode, including any warmup
effects. Hash equality alone does not meet the byte-comparison requirement.

## Pipeline attachment

Packet32 README describes one context and queue per rank, 24 owned layers and
two shared stream slots containing bytes. A recording belongs to that rank's
owner/context. One graph per parity can bind fixed local staging buffers; IPC
receipt and upload stay outside. Token/position/active/error and mutable state
live in rank-local device allocations. Shared memory contains no SYCL handles.

Reallocation, changed dispatch/kernel build, weights, geometry, context capacity,
format or rank ownership invalidates the recording. Parity chooses its already
qualified recording. Rollback changes device state before replay, not captured
host arguments.

## Implementation review

Reviewed bench.cpp and backend34.hpp independently of their author. Captured
production operations receive fixed Matrix/Spec and buffer addresses prepared
once from the packet29 path. The only host iteration variable enters Boundary
through an uploaded Control allocation and regenerated input banks; it never
enters the captured half as a scalar argument. Position, routes and attention
IDs are consumed through the existing device pointers.

The review found three gaps, now fixed in source:

1. Attention-count variation was not asserted. dynamic.jsonl now records every
   direct iteration's six QSA counts. Each list must be a valid sentinel prefix
   with IDs bounded by position, and its count must equal the declared
   position/budget formula. More than one count is required at completion.
2. Parity was consumed by Boundary but lacked an assertion. Boundary now checks
   its device output byte-for-byte against the uploaded selected bank and
   verifies position/active. Both parities are required. The README accurately
   identifies this operation as outside the recorded/timed half.
3. Both CPU mock modes previously traversed one undivided vector. MockRecording
   now partitions the deep-cloned commands into 24 layer groups and validates
   that partition before layer replay. It still intentionally models logical
   commands, not compiler-private kernel closure serialization.

Both replay paths restore the entire writable initial snapshot and compare
every mutable allocation with the direct result for that iteration. The
canonical direct result is restored before the next iteration. Immutable
weights and RoPE/constants are not included in writable-state comparison.
The capture occurs only after direct iteration 0 passes. Command capture
does not run the graph, so its repeated recordings do not mutate the device
state. A byte mismatch throws before starting the next replay mode.

The original source findings and subsequent fixes establish the intended
data path on CPU. Final gate receipts determine whether the runtime variation
and byte checks actually passed. Native graph behavior, current-kernel
subgroup/local-memory support and event profiling remain device-window gates.
