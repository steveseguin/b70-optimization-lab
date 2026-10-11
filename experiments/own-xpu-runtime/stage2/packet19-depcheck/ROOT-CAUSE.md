# Packet16 fault: CPU audit, not a proven native root cause

**No device ran. No captured mapping identifies a faulting application allocation.**
We reproduced uninitialized snapshot readback and repaired unchecked index paths.
Neither is established as the cause of the incident.

## Ranked candidates

| Rank | Candidate | Evidence and limit |
| --- | --- | --- |
| 1 | Native cross-device event or shared-context backing/mapping behavior | The first chain is begin.0(Q0) -> begin.1(Q1) -> broadcast(Q0), before layer23. Packet14 drains both owners before peer copies. Driver-owned event/synchronization storage with incorrect residency could explain both queues faulting. No captured allocation map proves this. |
| 2 | Corrupted index plus incomplete local guards | Standalone malformed-input tests expose tiny/serial QSA, gather-before-cast, and real attention_value guard gaps. Valid first-token indices are initialized and ordered; resident expert GEMVs already guard weight addresses with valid_route. No incident trigger was found; tiny geometry was not W2 geometry. |
| 3 | Application foreign binding, missing edge or premature release | None found by source audit or valid-input numeric sanitizer runs. One owner adds its global predecessor to every compute/copy, and native kernels pass dependencies onward. Context checks every compute binding's owning card. This does not prove the native implementation honors the DAG. |
| 4 | Existing fault state, driver/firmware or hardware-triggered cascade | The boot already had a fault. Both dumps report GuC70.44.1, wanted70.54.0. These are confounders, not diagnoses. Simultaneous symptoms do not logically exclude a cascade or shared recovery behavior. |

There is **no proven candidate that establishes both faults before any site
completed**. Unchecked Engine::enqueue emits no per-site timing/progress records.
Empty sites.jsonl is normal for this command. The evidence establishes no completed
token. There are two distinct addresses: 43:00.0 faults on 0x0000d556a9ed0000;
47:00.0 on 0x0000caac549d0000. Both VM dump captures end with `[0].error: -19`,
preventing allocation correlation. Snapshot times differ by 318,839 ns.

All incident files, including both complete coredump byte streams, are hashed
in [incident-inputs.json](incident-inputs.json). The readable-field extracts omit
only encoded GuC/CTB blobs retained in the original evidence. Those blobs have
not been decoded into a kernel/address attribution.

## Reproduced shipped violation

Engine::initialize allocates layer-snapshots without writing it. The step lambda
copies only layers executed on that card, then reads all 48 slices on both cards.
Real snapshots are 983,040 bytes: card0 never writes [491520,983040), card1 never
writes [0,491520). Mini has additional unused slices. Only populated slices are
hashed, explaining the old exactness pass. This is a never-written-byte read,
**not a missing edge** and not an index input. First prefill position0 does not
capture fixtures, so this does not explain a fault at the start of prefill.

[VIOLATIONS.md](VIOLATIONS.md) and the shipped mini/real-short reports enumerate every observed violation by
position/site/allocation. No foreign compute binding, RAW, WAR, WAW, pending
release or uninitialized index-input violation was observed on valid inputs.
Negative checker tests deliberately inject all those classes; their failures
must not be attributed to packet16.

## Submission and boundary evidence

[Independent audit](review-hazards.md) lists every operation expansion, owning
card/context, exact wrapper functions and streaming/resident differences.
The gzip JSONL traces record each CPU mock submission's queue, context,
allocation/range/read/write/index accesses and actual owner dependency list,
including initialization, H2D lookups, card crossings, sticky controls, router IDs
and fixture copies. `native-first-position-enumeration.jsonl.gz` expands the
shipped trace through position0 using the frozen native dispatch. Native split4
GEMVs become partial/reduction nodes with workspace ranges and the explicit
first-event plus owner-predecessor reduction dependencies. **This is source-derived
native enumeration, not recorded native execution under the checker.**

Every kernel/copy joins Eprevious in one shared owner ledger. Adapter entry,
ng kernel(s), and exit additionally pass their explicit predecessor. Host wait
plus synchronized event retirement establishes ordering before old IDs disappear.
H2D slab reuse waits for the copy. Snapshots precede the next streams overwrite
(WAR protected). Router -> gather -> expert projection is ordered. Layer23's five
peer copies and the head's two result/error copies use the same chain. Allocations,
slabs, queues and context survive pending work. Failures retain ownership.

The handoff copies error over the destination error slot, potentially hiding a
preexisting local error. Equal first-token positions/active values and host context
admission make no normal-flow trigger apparent. This is a diagnostic preservation
concern, not a demonstrated incident cause or missing edge.

## Changes and remaining uncertainty

1. Define snapshot bytes before any readback, preserving captured output hashes.
2. Guard IDs before conversion/address formation; set sticky error and use safe
   index0, or reject before addressing. Guard the serial Core too. Atomic error
   access and workgroup-uniform guard decisions avoid new divergent barriers.
3. Conservatively host-wait foreign-card events and omit them from native wait
   lists. Same-card native dependencies remain. This preserves ordering but
   changes synchronization/timing. It is **containment pending qualification**,
   not proof that cross-device SYCL events are intrinsically invalid or that the
   captured fault is fixed.

EnableDeferBacking=0 is not read by these application sources. Its effect on
internal event pools, USM backing and peer mappings **cannot be judged from this
code**. Packet14 passed without it, but did not test packet16's asynchronous
cross-card waits or 53 GB residency. CPU exactness and syntax-only native builds
do not authorize lifting FAULT HALT.

## First post-reboot device step

After the owner's reboot and coordinator admission, use the same shared-context
backend with only a few KiB of initialized local buffers:

1. Q0 local trivial kernel -> Q1 local trivial kernel -> Q0 local trivial kernel,
   using conservative host fences first. Verify canaries after each short segment.
2. Tiny bidirectional peer copies with local consumers and checked D2H canaries.
   Record allocation addresses/owners, event IDs/queues, wait lists, completion
   and exact environment; drain and release gracefully.
3. Only then admit a separate tiny two-card model. The original unfenced
   event-only chain is a separate diagnostic decision, never a silent fallback.

Use a bounded fault-watched window, no retries and no weights. Do not load 53 GB
before these small topology checks. No device step was taken here.
