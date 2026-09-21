# Packet 90 design: attribute and close the 0.7 s/pair packing loss (2026-09-21)

## Facts (from f87 endure receipts, 82 sampler receipts with emitted_phases)

Measured with `scripts/analyze-phases.py` against run dir
`encoder-server-graph-capture-87` (arm `f87-endure`), steady tail:

| Metric | Median | Note |
| --- | ---: | --- |
| Pair-job (`stage_seconds`) | 2.61 s | matches f84's 2.654 s |
| stage_a (48 blocks, latent res) | 1.64 s | 64% of the chain |
| upsample | 0.04 s | negligible |
| stage_b (48 blocks, upscaled) | 0.81 s | outliers up to 16 s pre-freeze |
| Per-clip chain | ~2.5 s | two clips -> 5.0 s of chain per pair |
| Pair wall (f86 endure) | 3.26 s | interval 1.63 s/clip |

Per-pair GPU work cannot exceed ~2.5 s per card if perfectly packed; the
observed 3.26 s wall carries **~0.7-0.8 s/pair of packing loss (22-25%)**.
Closing it: interval 3.26/2 = 1.63 -> ~1.25 s/clip (~20 fps). That is the
single largest untapped lever, bigger than every kernel fusion combined.

## Why current data cannot attribute it

`emitted_phases` uses event `elapsed_time` between phase marks on a stream -
a wall delta that *includes idle gaps*. It places time by phase name but
cannot say whether a card was busy or waiting inside the phase. Attribution
needs per-replay busy time.

## The measurement (packet 90, rides the next server after 89)
Implemented on branch `packet-90` (rides the next server build after 89):

- `ltx_graph_capture.py`: the hot replay in `GraphBlockRoute._call_native`
  is bracketed by an event pair on the issuing thread's stream; windows
  drain per receipt via `busy_window_report()` into per-`(device, route)`
  `{count, ms}` aggregates. Windows not yet complete at report time (the
  other clip still in flight) carry over in a pending list, never dropped.
  Capped ring (8192) bounds memory. Two event records per replay, sub-ms.
- `pipeline_sampler_node.py`: receipts gain `route_busy_ms` next to the
  existing `memory` snapshot (diagnostic-only guard, same as
  `loaded_models`).
- `analyze-phases.py` aggregates `route_busy_ms` across a run's receipts:
  per-card busy vs job wall, top routes by busy time.

No numerics change; no exactness risk. The CPU graph-adapter tests
(test-ltx-graph-capture-stdlib.py) pass on the branch.

With busy-vs-wall per card per phase, the loss attributes to exactly one of:

1. **Host-side boundary stalls** (`staged_move`'s `event.synchronize()`
   blocking the issuing thread). Weakened by arithmetic: ~2 boundaries x
   steps x 2 stages of ms-scale D2H waits sums to tens of ms, not 0.7 s.
   Fix if measured: `stream.wait_event` variant, keep the host issuing.
2. **In-phase card contention.** Both clips start chains together; each
   alternates xpu:0 (blocks 0-22) then xpu:1 (blocks 23-47). In phase they
   compete for the same card while the other idles. **Update after a
   segment-level simulation (f87 segment sizes, FCFS per card): strict
   per-card serialization walls at 3.39-3.85 s/pair - WORSE than the
   observed 3.26.** The xe co-run of contended streams is already beating
   forced serialization (~82% busy-card efficiency). A stagger/serialization
   gate is REFUTED as the fix; co-running must be made more efficient, or
   the dependency stalls filled with a third clip in flight.
3. **Serial non-block segments** (upsample, separate, noise, refills run
   alone on one card while the other idles) -> fix: prefetch/overlap the
   next clip's stage_a head against the current clip's tail.

Simulation-derived bounds: strict-FCFS 3.39 s/pair (best interleave) to
3.85 (naive); observed 3.26 implies real co-run gains. Perfect packing
bound from card demand (xpu:0 2.38, xpu:1 2.66 s/pair) is ~2.7 s/pair =
~1.33 s/clip (~18.8 fps) - reachable via a third clip in flight or
co-run efficiency, NOT via serialization. The busy-window measurement
decides which. Third-clip caveat: every sampler thread owns its static
buffers and graphs on BOTH cards, and xpu:0 is at 30.0 of 32.6 GiB
reserved with two threads - a third likely needs the split rebalance
(blocks off xpu:0) or a smaller per-thread buffer footprint first.

## What packet 90 is NOT

- Not QKV fusion (packet 85: ~1%, 2 GiB duplication, retired).
- Not transport (staged_move already ships probe-5's 1.68x recipe).
- Not step-count or resolution changes (quality-locked).

## Queue

1. Reboot (unblocks the sealed gate).
2. Packet 89 campaign: warm exactness gate + 30-prompt timing + 120 endure
   (wrong-clip hunt + fusion timing proof). Receipts carry emitted_phases -
   run analyze-phases.py on them as the baseline for 90.
3. Packet 90: busy-ms measurement -> attribution -> one targeted fix from
   the table above.
4. Re-measure; the floor discussion (0.74 s/clip weight reads) starts only
   after packing loss is under ~10%.
