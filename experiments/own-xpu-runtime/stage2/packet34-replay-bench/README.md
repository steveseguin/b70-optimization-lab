# Packet34: replay of a resident half token

This prepares one coordinator measurement of launch overhead on one B70. No
model weights are opened, no token is decoded, and no device ran during CPU
preparation. No speed is claimed.

The benchmark submits packet29's real measured kernel choices on synthetic
finite data. It links packet29's submission sources and uses its planner;
it does not replace the compute kernels with empty or simplified kernels.
Layers 24–47 give 18 GDN layers and 6 QSA layers. The last combine includes the
final.norm output that packet29 fuses into that same launch. The head, logits,
argmax, token lookups and cross-card transfers are outside this workload.
The source census counts 1,142 native kernel submissions over 878 logical sites.
R1 checks that count before replay. No native launch was executed to obtain it.
The host lowering has 1,064 submissions. The device path adds 78 finish
kernels for split GEMVs; the source census accounts for each one.

Four weight sets, layers 24–27, rotate over the 24 layers. They have distinct
deterministic bytes, real tensor shapes and original packed formats. The four
layer sets occupy 4,322,596,480 bytes, plus 40,960 bytes for the final norm.
Additional device allocations hold separate per-layer mutable state, scratch,
workspace, RoPE constants and control/input buffers. See allocation-census.json from
the CPU census for the complete device-byte accounting. The host creates at
most 4 MiB of packed weight bytes at once, with no full floating-point shadow.
The final device allocation total is 4,766,268,444 bytes, including the
expanded weight layouts required by the selected kernel variants.
directory.tsv contains metadata only; fixture-provenance.json binds its source.

The modes are:

- Direct: unchanged packet29 kernel submission entry points, one immediate
  SYCL submission at a time, with individual event profiling.
- Graph whole: one recorded SYCL command graph for the full half token.
- Graph layer: 24 recorded SYCL graphs, executed in the same layer order.
- Raw: unavailable. The inherited typed Level Zero bridge does not describe
  the current private packet29 kernel closures. review-raw-abi.md gives the
  exact blocker and gate result. There is no guessed native argument packing.

All modes share allocations. Every one of 210 iterations first runs direct,
then each replay mode starts from exactly the same saved writable state.
The first 10 iterations are warmup; 200 are measured. Every mutable buffer is
compared byte-for-byte after each replay, including scratch and control bytes,
and a final SHA-256 is reported. A mismatch stops before the next mode.
A replay never executes before its direct equivalent passes in that process.

The uploaded control and two input banks change each iteration. A small
device boundary operation selects an input bank using the uploaded parity
and writes device position. That operation is outside recording and timing.
The recorded half uses fixed addresses whose contents change: real router
kernels compute expert IDs and real attention kernels derive active slot
counts from device IDs and position. This demonstrates varying device inputs;
it does not claim packet29 compute kernels have a dynamic pointer selector.
Each iteration logs both ordered route IDs and sorted expert-set hashes.
The gate requires changing expert sets, so a change in order alone cannot pass.
See review-token-data.md for the trace through those consumers.

The actual dependency policy is one in-order queue. The owner chains logical
event handles, but the packet29 resident backend validates their card identity
and supplies an empty SYCL dependency vector. There are no cross-card events
or parallel layer branches in this benchmark.

For each iteration, the output records host wall time from first submission
to host-observed completion, submitting-thread CPU time, submission count,
and direct-mode per-kernel GPU durations and their sum. Control upload,
boundary operation, snapshot, restore and comparison are outside that interval.
This isolates submission cost; it is not a decode speed or end-to-end serving
measurement.

Replay pays only if bytes remain identical, memory stays bounded, and replay
wall time per half token is at or below direct's summed GPU time under the
registered comparison. That last condition is intentionally strict: a lower
submission count alone is not success.

Whole-half and per-layer graph sets are each recorded three times, retaining
the copies to expose cumulative growth. Record/finalize wall time, process
RSS, allocation accounting and the extension's required-memory query are
reported. The optional installed free-memory counter is queried only on the
owner's device. If unavailable, driver-private allocation pools remain unknown
and the bounded-memory verdict stays pending. No extra discovery is performed. A graph allocation bound stops the
experiment rather than repeatedly recording until memory is exhausted.

CPU gates use the real host arithmetic at tiny geometry, both host compilers
and fresh processes. The mock recorder deep-copies logical launch commands
and prepared bindings. It is a capture-value/state oracle, not proof of the
compiler's private SYCL closure ABI or native graph execution. Production
shape census does not execute arithmetic. Build and gate receipts carry
counts, compiler/link precision flags and binary hashes.

Use WINDOW.md for K0 compile smoke and the coordinator's R1 invocation.
DEADLINES.md and LIFETIME.md describe cooperative cancellation and object
ownership. A busy or uncertain child is retained for its coordinator.
INTEGRATE.md describes a future per-rank attachment; packet32 code is not a
dependency. Device correctness, graph extension support and performance remain
open until the coordinator runs the window.

CPU-only rebuild and gates, run sequentially from this directory (the installed
Intel compiler path is pinned in build.py). These commands never run either
device executable. Keep the inherited CPU affinity.

```bash
for mode in host icpx-host asan device; do
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B build.py "$mode" || break
done
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B cpu_gates.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B capture_gate.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B test_lifetime.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B test_window.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B raw_abi_gate.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B cleanup.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B seal.py
```

Stop on any failed command. Existing gate output directories must be archived
and removed by cleanup.py before a fresh repeat; do not overwrite evidence.
