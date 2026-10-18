# Packet58 cache and pointer CPU gates

The cache implementation is original lab code. Credit Niko1221 / Strata for
its published hot-expert GPU cache idea. No external implementation was used.

`cache_table.hpp` owns metadata only. Its global LRU uses variable-sized,
256-byte-aligned extents inside an externally owned byte arena. Each resident
entry covers gate, up and down together; the layer-2 IQ3_S expert has its own
larger extent. Free extents coalesce. This avoids charging every ordinary expert
for the exceptional layer's size. Empty initial placement is deterministic and
independent of the requests. Cache admission changes immutable weight location,
never tensor values or prompt/KV/answer state.

The transaction order is:

1. `begin_position` freezes the live table and returns a monotonic epoch.
2. `finish_position` requires that epoch and a completed compute fence.
3. `prepare` stages the next table, LRU and ordered fill list. Live slots may
   now be overwritten, so no next position may start.
4. The adapter submits fills in order, waits for all copies, publishes all
   projection pointers and generations, then waits for publication.
5. `commit` requires the epoch and both completion fences before another
   position can start. An overwritten victim is never restored after failure;
   failed work drains all queues and closes.

The C++ CPU model receives boolean completion claims. It rejects false claims
and wrong phases/epochs; **it cannot verify a hardware event**. The native
adapter must derive each true claim from its owned queue's actual completion.
Pinned sources, cache arena, route buffers, table buffers and copy staging
remain live through those fences. Entry generations change on eviction and
readmission, including reuse of the same extent (ABA). Native table mutation
must never overlap a consuming kernel; generation fields alone are not a
replacement for the publication fence.

`cpu_cache_gates.py` builds serially and runs two fresh processes each in
normal and AddressSanitizer/UndefinedBehaviorSanitizer modes. All weights are
small synthetic fixtures; there are no model reads, pinned allocations, device
queries, services or host-setting changes. Build scratch is removed after use.
The receipt hashes every local compiler dependency, binaries and compiler flags.

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet58-onecard/cpu_cache_gates.py \
  --output experiments/own-xpu-runtime/stage2/packet58-onecard/evidence/cache-cpu-gates-fresh.json
```

Use a new output path. The state gate checks 800 randomized positions with a
4 KiB arena and verifies every live pointer's bytes after each transition. It
also checks variable extents, LRU versus frequency, empty/oversized caches,
invalid expert IDs, pointer/extent overflow, stale generations, epochs,
unfinished compute/copy/publication, and host-memory lifetime on failed fills.

The expert gate uses **36 complete expert cases**: IQ2_S or IQ3_S gate/up,
unchanged BF16 SiLU/product, and IQ4_NL down, at production widths and row
counts. Each format tests all misses, all hits and mixed pointers, with six
input/route scenarios: ordinary, partial rows with nonzero row starts,
invalid expert IDs, signed zero/subnormals, NaNs, and infinities. Every output,
route status and sticky error is compared byte-for-byte to the frozen
packet49d production host kernels. The reference translation unit renames its
changed namespaces to prevent a linker from accidentally substituting the
candidate implementation through C++ template/ODR merging.

Raw exceptional results remain exact comparisons within each compiler build.
As in packet49d's gate, NaN/Inf scenarios are excluded from the portable
cross-compiler digest because equivalent host compiler settings can choose
different NaN payloads. They are never compared with a numerical tolerance.
The first harness attempt included those scenarios in its portable digest:
all within-build comparisons passed, but the normal/sanitized digests differed.
The corrected portable digest has an explicit exclusion field. An earlier
compile attempt also exposed a missing include search path; it was corrected
without changing the production reference.

These are CPU pointer-placement and state-machine proofs. They establish
neither zero-copy support/performance nor full-model/native exactness. The
coordinator's K1, KD/W2m and complete realistic-suite windows remain necessary.
The cache updates between positions, so packet55's trace hit rate is planning
evidence; actual delayed-admission hit rates must be measured here.
