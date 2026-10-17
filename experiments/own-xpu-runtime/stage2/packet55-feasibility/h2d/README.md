# Packet55 expert streaming microbenchmark

Prepared with CPU compilation and CPU wrapper tests only. No GPU measurement
has run. All bandwidth, latency and overlap results remain pending.
The code is independently written in this repository. Niko1221 / Strata
inspired the cache plus CPU-miss design; no external inference code is used.

`stream_bench.cpp` explicitly creates a Level Zero queue from a group with
`COPY` capability and **without** `COMPUTE` capability. It records the ordinal
and queue index and refuses a compute-engine fallback. A separate SYCL
compute queue uses the same native context and device. Physical card 2 must
resolve to `0000:43:00.0`; card 3 must resolve to `0000:47:00.0`.

Each run covers 4–10 slabs of both 1,971,200 bytes (ordinary IQ2_S/IQ4_NL expert)
and 2,329,600 bytes (exceptional layer-2 IQ3_S/IQ4_NL expert). Each batch is
measured both as one contiguous transfer and as one command per slab. The
second is the closest microbenchmark to scattered expert addresses. Neither
includes packing scattered pageable expert backing into pinned staging.
That host gather cost must be measured and charged before engine admission.

For every shape, run three warmup trials and 30 measured trials of copy only,
compute only, and concurrent copy plus compute. Rotate trial order. A changing
byte pattern and poisoned destination prevent stale-data/no-copy success;
full-byte comparison stays outside timing. Compute is a fixed arithmetic
recurrence on 32,768 work items; its event duration and a finite output check
are recorded. It is a synthetic compute contention test, not an expert kernel
or a claim that model execution overlaps equally well.

The device copy interval is bracketed by Level Zero global timestamps and
barriers. It includes command/barrier gaps, not only active DMA. Its tick width
and nanoseconds per tick are obtained from `zeDeviceGetProperties` and wrap is
handled. Compute uses SYCL event duration. The clocks' epochs are never
subtracted from one another. Wall intervals include submission and completion.
“Route-known to slab-resident” begins before command-list reset and construction
and ends after the copy queue reports completion. Payload filling, destination
poisoning, compilation and readback are outside that interval. Router execution,
route D2H, eviction and pageable-to-pinned staging are also outside it and must
be added in the engine design.

The summary records two overlap diagnostics:

- Effective overlap fraction: `(copy_wall + compute_wall - concurrent_wall) /
  min(copy_wall, compute_wall)`. These are separate trial medians. It is not
  clipped: negative values show slowdown and values above one expose variation.
- Per-trial envelope overlap lower bound: `max(0, concurrent_copy_envelope +
  concurrent_compute_event - concurrent_wall)`, then median. This needs no
  common-clock epoch. A zero lower bound is inconclusive. A positive value
  establishes overlapping measured envelopes, not a hardware utilization trace.

The maximum **pinned host allocation is 23,300,096 bytes**: ten exceptional
slabs plus one 4,096-byte timestamp page. Pageable readback is 23,296,000 bytes;
explicit device allocations total 23,427,072 bytes. Runtime/compiler/driver
memory is additional and is monitored. No weights are opened, no full expert
bank is pinned, and no host-memory setting changes.

CPU-only preparation (one compiler owner at a time):

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet55-feasibility/h2d
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest discover -s "$P" -p test_h2d.py
```

The coordinator runs two fresh windows, sequentially, when the selected card
is free. Set `LIB` to the approved runtime library path and `REVIEW` to the
actual reviewed past UTC kernel-fault boundary. The commands intentionally
supply no invented boundary. Card 3 can replace card 2 in both commands.
Allow **1–3 minutes each**, with a 600-second supervised limit; this estimate
is not measured. No automatic retry. The coordinator may allow unrelated
packet49d work on cards 0+1, but should record that contention and use quiet
H2D windows for the final transfer design numbers.

```bash
systemd-run --user --wait --unit=packet55-h2d-a --property=KillMode=none \
  bash "$P/coordinator.sh" "$LIB" "$REVIEW" 2 "$P/evidence/h2d-a"
```

Only after safe successful completion:

```bash
systemd-run --user --wait --unit=packet55-h2d-b --property=KillMode=none \
  bash "$P/coordinator.sh" "$LIB" "$REVIEW" 2 "$P/evidence/h2d-b"
```

The wrapper checks exact source/binary hashes, nice/affinity, the unchanged
memory-block fence, passive selected-card clients, disk and host headroom, and
the reviewed kernel journal. It holds the packet-wide `window.lock` throughout.
That local lock excludes packet55 route/CPU benchmark windows; it cannot exclude
other runtimes, so the coordinator retains physical ownership responsibility.
Unknown-PCI visible Xe clients are refused; inaccessible processes are recorded
and remain the coordinator's responsibility. Faults trigger cooperative stop
and retained evidence, never a hard kill, reset or restart. An undrained device
owner is retained for the coordinator. Preparation does not run these commands.

Each window automatically writes `summary.json`. Offline regeneration:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --run "$P/evidence/h2d-a/run" --output "$P/evidence/h2d-a/summary.json"
```

Take a conservative value across both fresh windows for feasibility estimates.
Do not interpolate unmeasured batch sizes or substitute these diagnostics for
one-card model speed or correctness measurements.
