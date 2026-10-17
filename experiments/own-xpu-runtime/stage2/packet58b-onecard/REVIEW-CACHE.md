# Packet58 independent cache/queue review

CPU-only review by the cache/gates subagent, separate from the engine author.
No device was opened. Reviewed `single_device.cpp`, `owner.cpp`,
`owner_retire.cpp`, `prepared_submission.hpp`, `main.cpp`, the indirect
submitters and K1 fixture. Status is conditional on the fixes and native
windows below; this is not a device qualification receipt.

## Proven by CPU gates

The [source-bound gate receipt](evidence/cache-cpu-gates.json) contains eight
fresh processes: two runs of each state/expert gate in ordinary and
AddressSanitizer/UndefinedBehaviorSanitizer builds. Each state run passed
213,816 checks over 800 positions and 3,740 evictions. Each expert run passed
396 comparisons across 36 full expert cases (1,522,656 compared bytes),
including ordinary IQ2_S and exceptional IQ3_S gate/up, IQ4_NL down, all-hit,
all-miss and mixed pointers. The portable digest agrees across builds and
fresh processes. Exact nonfinite comparisons remain within each compiler;
the explicitly excluded portable-digest scenarios are described in
[CACHE-CPU-GATES.md](CACHE-CPU-GATES.md).

## Successful-path ownership and ordering

- `CopyEngine::copy` appends the last owned event to each copy's dependencies.
  The dedicated copy queue waits on the producing compute event. The compute
  queue receives a barrier depending on the copy before any subsequent
  ordinary or prepared kernel. These form a one-way chain, not a cycle.
- `Engine::drain` waits its tail, then `retire_completed_events` refuses any
  pending tracked event and synchronizes the backend before removing IDs.
- Cache victims are overwritten only after a complete position drain, and the
  next position cannot begin until copies and table publication drain. Thus
  in-place device-table publication is safe; it does not need atomic pointer
  swaps while no kernel can read it. Per-entry generations remain diagnostic
  identity, while the actual queue fence establishes device visibility.
- Pinned expert banks, pointer tables and the cache arena are process-lifetime
  allocations. Table staging is filled in disjoint slices, retained until all
  table copies drain, and never reused while a copy owns it.
- The 48 route sources have separate named allocations from the plan; they
  are not scratch aliases. End-position readback therefore retains each
  layer's actual selected IDs.
- Request reset clears mutable allocations, history, lookup staging and
  active/error state without replacing allocation IDs. Immutable expert
  banks/cache/tables survive. Kernel captures retain their original buffers.

## Findings sent to the engine author

1. **Copy submission failure gap.** The initial `copy()` implementation
   submitted DMA, then a compute-queue barrier, then recorded the DMA event.
   If barrier submission threw, the DMA had not entered the owner's ledger.
   The owner's shutdown error path could observe zero tracked work. Requested
   fix: after a successful DMA submission, either retain that event or
   positively drain it before propagating any bridge/record failure; inability
   to prove completion must retain the owner for the supervisor.
2. **Both queues must drain on an asynchronous error.** The initial
   `synchronize()` called `wait_and_throw()` on the copy queue first. A throw
   skipped waiting on the compute queue. Requested fix: wait both queues before
   surfacing asynchronous errors, retaining ownership if completion cannot be
   proved.
3. **K1 must measure PCIe reads rather than repeated-address cache hits.**
   The initial timing loop reused approximately 9–14 MB banks for all 20
   iterations. A GPU hardware cache can satisfy repeated immutable-weight
   reads, so the resulting bandwidth can misselect zero-copy. Requested fix:
   rotate distinct pinned banks beyond the device cache, or use a distinct
   bank for every timed iteration, record the working set and count all bytes.
4. **Streamed-path epoch receipts.** The fallback drains correctly but initially
   remained in metadata epoch zero for every layer. Recommended advancing a
   checked epoch at each drained layer boundary so receipt generations and
   fault localization distinguish admissions. This is diagnostic hardening;
   the existing explicit drain is the hardware lifetime protection.

5. **Pinned-memory summary inherited from the two-card engine.** The initial
   `memory.json` hard-coded 4,194,304 pinned bytes even though the new expert
   backing alone is 48.6 GB. Requested fix: derive the summary from
   `arena.total(Memory::pinned)` before shutdown, matching the allocation census.

Re-review confirms findings 1 and 2 were fixed in source. The DMA/barrier and
record operation now share a protected try block. On failure the submitted
copy has a bounded 60-second completion check; uncertainty retains the owner.
Both queues now finish before asynchronous errors are surfaced. Finding 3's
zero-copy timing uses distinct pinned regions 1 through the iteration count,
with region zero reserved for the exactness/compile pass and a working set of
at least 128 MiB per projection. The author also assigned disjoint regions to mixed and streamed timing
(`N+1..2N` and `2N+1..3N`), and poisoned the VRAM destination before the
streamed copy correctness check. Finding 4 remains diagnostic hardening.
Finding 5 is fixed: `memory.json` now uses the actual pinned arena total.

These are source-review conclusions; no exception path was injected into a
real device, and no native copy/compute measurement has run here. No parent
packet or protected tree was edited for this review.

## Still needs coordinator evidence

K1 must establish that host-pinned USM is device-readable, that hit/miss/mixed
outputs match direct production kernels, and that the distinct-address host
read rate chooses the miss path honestly. KD/W2m must compare all target
layers and generated tokens to the unchanged packet49 oracle. Fresh complete
suite windows must establish one-card determinism, actual cache hit/fill
rates, prefill/decode time, host/GPU peaks and graceful teardown. CPU evidence
cannot establish any of those native results.
