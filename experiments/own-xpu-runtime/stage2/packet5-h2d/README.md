# Packet 5 — measured transport preparation

The first coordinator run on card 3 stopped before completing any case;
the timing fix below is CPU-tested and compiled, with its device rerun pending.
There are no measured GB/s or overlap claims yet. This is the first transport measurement needed by
[ONE-CARD-PLAN](../ONE-CARD-PLAN.md), using our `Device`, `Arena`, `CopyEngine`
and shutdown protocol, with the unchanged [packet 2 GEMV](../packet2/kernels/device.cpp).
No torch, vLLM, model files, downloaded code or server is involved.

## October 11 timing failure and fix

The 03:10 UTC card-3 run returned `nonpositive profiling interval`, with no
completed cases or overlap rows. Both in-order queues already had
`enable_profiling`; the bug was requiring every copy event to have a positive
interval, including setup copies. The receipt did not save the offending
timestamps, so it cannot distinguish zero from equal or reversed timestamps
or establish the backend cause. The [native receipt](data/card3-20261011T031020Z/native.json)
records complete teardown, `safe_to_exit=true`, zero live bytes and zero
in-flight events; the [window log](data/card3-20261011T031020Z/kernel-window.txt)
has no fault lines. The failed [window](data/card3-20261011T031020Z/window.json)
and its [original build identity](data/card3-20261011T031020Z/build-receipt.json)
are retained unchanged. The old build is preserved locally in
`build/prior-20261011T031020Z/`.

Both queues still enable profiling, and the profiling query now checks both.
Missing profiling information and zero/nonpositive event intervals no longer
abort a copy: raw timestamps remain, and `duration_ns` is null for invalid
intervals (an unavailable profiling query records zero timestamps).
Only SYCL's profiling-unavailable error is optional; execution errors still fail.
Each measured repetition retains its steady-clock wall time around submission
and completion, including intermediate chunk waits and profiling queries.
The receipt adds nullable `event_ns`, `event_payload_GBps`, and `wall_GBps`
for every transport repetition, both median rates per case, and
`repetitions_without_event_timing` for transport and overlap rows. Any missing
chunk invalidates that repetition's event total; it never becomes a partial
bandwidth estimate. Event medians use valid repetitions only, or null if none
exist. Every wall sample remains included. The combined overlap interval and
ratios use wall time; event-overlap fractions are separately nullable with
their own missing-repetition count. Ownership, teardown, fault watching and
the 120-second admission bound are unchanged. No device was opened for this fix.

## Sizes and bounded work

[plan.json](plan.json) is derived from the complete, SHA256-bound
[IQ3 census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json).
UD-IQ3_XXS is the release name; its expert tensors actually have these grids:

| Layers | Gate | Up | Down | One triplet | Ten triplets |
| --- | ---: | ---: | ---: | ---: | ---: |
| 47 ordinary layers: IQ2_S/IQ2_S/IQ4_NL | 524,800 B | 524,800 B | 921,600 B | 1,971,200 B | 19,712,000 B |
| Layer 2: IQ3_S/IQ3_S/IQ4_NL | 704,000 B | 704,000 B | 921,600 B | 2,329,600 B | 23,296,000 B |

Also measure **64 MiB = 67,108,864 B** and **256 MiB = 268,435,456 B**.
Ten experts are one token's selected experts **in one layer**; all 48 layers
read 949,760,000 active expert bytes per token. Gate/up/down bytes are packed
contiguously into one synthetic transfer payload, not three launches or a
host gather. The bytes include quantization scales. Actual model gathering,
routing and packing costs need a later measurement.

For each of six sizes, run exactly 20 measured repetitions of pinned H2D,
pageable H2D, pinned D2H, pageable D2H and same-card D2D. With two explicitly
admitted cards, also run 20 host-bounce A→B repetitions at every size:
A D2H → ordinary CPU memcpy between separately owned pinned slabs → B H2D.
This chooses the allowed bounce path, without probing direct peer support
or handing one owner's pointers to another owner. Receipt wall bandwidth
counts one delivered payload; link traffic is explicitly **twice** that size.
Per-leg events and CPU memcpy time are retained; clocks on different cards
are never subtracted from one another.

All copies pass through `CopyEngine`. Its 128 MiB per-copy bound and two
in-flight-event bound remain. A 256 MiB case is **two serialized 128 MiB
chunks**, so its wall time includes the intermediate wait. No individual
256 MiB mapping is submitted. Each case changes the source byte pattern,
pre-touches the full host region, and checks all destination bytes after its
20 repetitions. Setup uploads and verification readbacks are outside timing.
These are repeated-buffer transport diagnostics, never cold model benchmarks.

## Copy/compute overlap

[independent-queues.patch](independent-queues.patch) is a focused overlay on
our lab's [pinned stage 1 packet 3 sources](owner-source.json), applied only to this packet's ignored
`build/owner/`. Shared source files and default scheduling stay unchanged. The pinned Git
objects make the patch independent of concurrent, uncommitted sibling edits.
The overlay includes the small event-profiling API needed for timings, adds
a second owned, in-order profiling queue for copies and
an explicit `Device(..., true)` opt-in that removes the implicit preceding
submission dependency. Explicit dependencies, the global event ledger,
backpressure, allocation lifetimes, final marker and both queue drains remain.
The caller must supply dependencies for shared buffers; this harness uses
fully disjoint copy and GEMV buffers and waits setup transfers before compute.
The same owner owns both queues and one selected-device Level Zero context.

At every size, run 20 repetitions each of copy-only, compute-only, serialized
copy then compute, and concurrent compute plus pinned H2D. Compute is the
packet 2 IQ2_S 640×2560 gate GEMV, subgroup 16, with synthetic valid packed
blocks and BF16 zero activations. The expected output is checked exactly;
this is an overlap load, not model-output qualification. One untimed GEMV
initializes JIT before measurement. There is only one compute queue; the
second queue submits copies, not another concurrent compute workload.

The runtime chooses the hardware engine for SYCL memcpy. Two queue objects
alone do not establish bcs use or overlap: **zero overlap is a valid result**.
This tests the [design's copy-engine overlap claim](../../DESIGN.md#platform-and-implementation-boundary),
without claiming additional compute concurrency or forcing a driver setting.
The receipts retain runtime environment and both queues' event intervals.
No power, driver, host-memory or `EnableDeferBacking` setting is changed.

`overlap_ratio = median(serial wall) / median(concurrent wall)`; greater than
one is a wall-time gain. Also report isolated-copy-plus-compute / concurrent,
and the intersection of concurrent copy/GEMV event intervals divided by the
shorter total event duration (0 means none, 1 fully overlaps the shorter work).
Event overlap uses one card's shared profiling clock. Submission latency,
one-millisecond completion polling in our wrapper, profiling queries and
intermediate chunk waits all remain in wall time. Device event GB/s excludes
these costs, queue gaps and pageable staging outside command execution;
therefore event GB/s alone is not end-to-end expert streaming performance.

## CPU validation and build

From the repository root, using the existing compiler and Python jsonschema:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet5-h2d/plan.py --dry-plan
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet5-h2d/validate.py
```

The validator runs Python plan/schema/metric/fault-protocol tests and host-only
mock ownership tests. It compiles and links the SYCL binary with installed
icpx 2026.0.0, `-fsycl`, strict math and two build workers. It never executes
or enumerates through that binary. Build commands, compiler commands, source
hashes (including the CPU-tested timing header), patched-source hashes, binary hash and test output are saved in
[build-receipt.json](build-receipt.json). Default validation deletes its entire
owned build scratch (`build/owner/`, `build/compile/`, `build/plan.tsv`) after
recording evidence; prior run evidence and archived builds remain untouched.

## Coordinator command — physical card 3 admission first

The coordinator supplies an exclusive native window, current host-halt
resolution, fresh health and host/device-memory admission, and verifies that
unmasked Level Zero index **3** is the intended physical card. An authorization
flag does not substitute for those checks. This preparation launches nothing.
No masked selector environment is accepted, to avoid silently renumbering cards.

Requested peak: card A **537,402,112 device B + 268,435,456 pinned B +
268,435,456 pageable B**; optional card B adds 268,435,456 device B and
268,435,456 pinned B. Driver shadows and runtime/JIT/codebook overhead remain
unknown, not zero. The allocation census and before/after host meminfo are
retained; these are not peak RSS measurements. The lab's
[host-shadow note](../../../../docs/host-stability-and-fault-diagnosis.md)
records `EnableDeferBacking` effects; do not assume that multi-card finding
applies to this small single-card owner or alter it during this experiment.

First rebuild with the compiled target retained (CPU only). Its three build
scratch paths must not already exist; preserve prior builds and run evidence
before clearing those paths. Existing run directories under `build/` are allowed.
Then set up the installed oneAPI runtime in the coordinator's shell; the
[passed native smoke](../../stage1/packet3-prep/README.md#first-native-execution--pass-2026-10-11-0153-utc-boot-13858eef)
records the UMF dependency supplied by setvars.

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet5-h2d/validate.py --keep-build
source /opt/intel/oneapi/setvars.sh
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet5-h2d/device_window.py --authorized-device-window --card 3 --admitted-cards 3 --seconds 120 --output experiments/own-xpu-runtime/stage2/packet5-h2d/build/card3-timing-fix
```

If exactly cards 3 and 2 are both admitted, change `--admitted-cards 3` to
`--admitted-cards 3 2` and use a fresh output directory. A remains card 3; B
becomes card 2 and the bounce cases run automatically. No other card is used.
There are no automatic repeat launches or retries.

The watcher reuses packet 2's journal cursor reader and specific fault regex,
verifies source/binary/plan hashes, saves boot/PID/card identity, and launches
one child. New faults, lost journal access, timeout or signals persist a STOP
latch and send one SIGTERM to the captured PID. The child checks stop/deadline
before every allocation/submission and waits each event for at most five
seconds. It writes partial evidence after every completed case and before
teardown, then drains, releases storage, waits the idle marker and closes both
queues and the native context. An incomplete or failed teardown retains
ownership for the coordinator. There is no forced kill, restart, reset or reboot.

The **120 s cap bounds admission of work**, not a blocked driver call or
forced process lifetime. Five-second drain waits and a five-second journal
postflight can extend elapsed time. As in packet 2, a stuck driver retains its
owner while the watcher keeps collecting evidence. Stop/recovery belongs to
the coordinator. The external idle/health check is still required after a
clean process exit; watcher success alone cannot qualify the machine.

## Receipts and how the numbers change the one-card plan

`native.json` retains device name/index/driver/UUID, every size, 20 raw wall
samples and SYCL start/end timestamps with nullable event durations per case, byte-check status, overlap
arms, requested allocation census and per-owner teardown. `receipt.json`
adds decimal GB/s, overlap ratios, exact census provenance and streaming
arithmetic. [receipt.schema.json](receipt.schema.json) checks structure;
[receipt.py](receipt.py) also checks case/event coverage, derived math,
identity, allocation totals and ordered safe teardown. `window.json` and the
kernel logs independently record fault/deadline status. Incomplete runs keep
partial native evidence and cannot produce a validated success receipt.
A measured receipt with `window_passed=false` is failed-window evidence.

For active missing expert bytes `B` and measured bandwidth `R` in decimal GB/s:
**transfer seconds/token = B / (R × 10^9)**, and the transfer-only token ceiling
is its reciprocal. For all misses, sum **47 × 19,712,000 / ordinary-top10-rate
+ 23,296,000 / layer2-top10-rate**, converting rates to B/s. The receipt reports
this separately for pinned and pageable wall rates. A one-expert or 64/256 MiB
rate must not silently replace those actual top-10-size measurements.

Use these observations to replace the historical ~19 GB/s migration and
~7 GB/s paging *scenarios* in ONE-CARD-PLAN. Keep the old provenance visible.
Resident dense weights need no expert H2D traffic; a cache changes the missing
bytes according to observed routing, not the copy rate. Host gathers, routing,
cache misses, GEMV and dependencies still add time, and the current-layer
copy/compute overlap test does not demonstrate next-layer prefetch or full-model
throughput. The packet produces diagnostic transport evidence, no speed headline.
