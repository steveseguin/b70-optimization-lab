# Second-queue quantize overlap: CLOSED NEGATIVE - B70 has one compute engine, so a second SYCL queue cannot overlap compute at all

Date: 2026-08-23. Closes the arc preregistered in
[the second-queue design note](2026-08-22-qwen38-q4km-tp1-second-queue-design.md).
Patch (tracked, not landed): [`llamacpp-q8-quant-prefetch-second-queue-candidate-20260823.patch`](../patches/llamacpp-q8-quant-prefetch-second-queue-candidate-20260823.patch).
Raw gate runs: `bench-results/.../q8prefetch-gates-20260823/`.

## What was built

`GGML_SYCL_Q8_QUANT_PREFETCH` (default 0) on a scratch worktree build of the
promoted TP1 lane (`fa0f3b25a` + patch): memo-miss q8_1 quantizes submitted on
a real second in-order `sycl::queue`, gated on a per-producer completion event
(recorded per node in `graph_compute_impl`), with the consumer GEMV ordered
behind the quantize by an event barrier, pending-event protection on memo slot
reuse/free/teardown, an engagement counter, and a poison door
(`GGML_SYCL_Q8_QUANT_PREFETCH_POISON`) that drops dependencies and delays the
second queue.

## Gate ledger

Preregistered gates, amended 2026-08-23 with user sign-off: oracle-hash
identity was re-scoped from "vs the registered promoted-binary oracle" to
"within the same binary", because icpx `fp-model=fast` makes ANY rebuild
numerically non-identical to the promoted binary (see Unsatisfiability below).

| Gate | Result |
| --- | --- |
| 1. No-op door | **PASS (strongest form):** patched build door-off = clean same-commit rebuild, 12/12 output hashes |
| 2. Bit-exact (amended: within-binary) | **PASS:** door-on = door-off, 12/12, with the mechanism fully engaged |
| 3a. Race-clean stress | **PASS:** 8/8 full-suite repeats hash-identical under the door |
| 3b. Poison red control | **COULD NOT GO RED - diagnostic, see below** |
| 4. Win threshold (+2% LB) | **FAIL: -2.37%.** off `27.819/27.824`, on `27.160/27.159` tok/s conventional (quiet box; on-pair spread 0.004%) |
| 5. Mechanism counter | **PASS:** `prefetch_launches=667453` over 5917 graphs = 112.8/graph, `no_producer=0`, `stalls=0` |

## The decisive finding: one CCS

The poison control could not go red: with every consumer barrier dropped AND
the second queue artificially delayed (its work visibly throttled the whole
server to ~0.7 tok/s), a bounded greedy completion still matched the
unpoisoned door-on output exactly, and `prefetch_stalls=0` in every run.
Together with the speed signature (pure overhead, no overlap benefit), this
is only consistent with **global submission-order execution across both
queues**. Hardware confirms it: the B70 exposes exactly one compute command
streamer (`/sys/class/drm/card0/device/tile0/gt0/engines/` = `rcs`, `bcs`,
**one `ccs`**). Every compute kernel from every SYCL queue funnels through
one hardware FIFO in submission order:

- there is no compute/compute concurrency on this device, ever;
- a missing cross-queue dependency cannot race (which is why red was
  impossible);
- the only thing a second queue adds is orchestration cost - measured at
  ~0.87 ms/token for ~113 prefetches/graph, i.e. ~8 us per extra L0
  immediate-command-list submission (4 per prefetched call).

So the design's premise (hide the ~25 us/call quantize tax behind concurrent
GEMVs) is not implementable on B70 by ANY second-compute-queue scheme,
however cheap the orchestration. The remaining levers on the quantize pool
are: cheaper quantize kernels, merging quantize launches (fewer dispatch
gaps), or the copy engine (`bcs`) for transfer-shaped work only. Producer-side
fusion stays rejected (fp-model=fast exactness, q8out note).

## Rebuild-oracle unsatisfiability (affects every future lane-source arc)

A clean rebuild of the EXACT promoted commit scores 0/12 against the
registered oracle while matching a second rebuild 12/12: `fp-model=fast`
codegen is stable within a build but not across builds. Consequence: any
source-change arc on this lane MUST gate exactness within-binary
(off-vs-on + N-run stress + quality battery), and a promoted-binary oracle
can only bind the build it was captured from. Conventional SPEED transfers
cleanly (rebuild door-off = `27.819/27.824` vs promoted `27.814/27.825`).

## Traps hit (operational)

- `systemd-run --user` dies silently when the idle login session's user bus
  goes away mid-campaign; gate legs must not depend on it (direct-exec
  variant used, memory caps lost - acceptable for gates).
- A script-relative helper path (`verify-model-direct.sh`) broke when the
  repro server script was copied for the direct-exec variant.
- First poison delay (50M-iteration single_task) was ~100x heavier
  on-device than estimated and blocked warmup entirely; poison delays must
  be sized against GPU single-thread speed, and the slot-reuse safety
  barrier (correctly) throttles the whole pipeline once the second queue
  lags.

## Disposition

Arc CLOSED as a measured negative with a hardware root cause. The door
stays default-off; the patch is preserved as a tracked diff only (not
landed in the lane repo). Do not re-attempt compute/compute overlap schemes
on single-CCS devices; re-evaluate only on hardware exposing multiple
compute engines.
