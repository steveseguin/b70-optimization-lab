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

In `GraphBlockRoute._call_native` (ltx_graph_capture.py:796): bracket every
graph replay with a pair of events on the thread stream, accumulate
`busy_ms` per `(card, route)` into a module-level counter. The sampler node
already snapshots module state into its receipt (`report['memory']` etc.) -
add `report['route_busy_ms']` alongside. Host-side cost: two event records
per replay (sub-ms), one dict add. No numerics change; no exactness risk.

With busy-vs-wall per card per phase, the loss attributes to exactly one of:

1. **Host-side boundary stalls** (`staged_move`'s `event.synchronize()`
   blocking the issuing thread) -> fix: `stream.wait_event` variant, keep
   the host issuing. Validate on the probe harness first.
2. **Phase misalignment** (both clips want the same card in the same
   windows) -> fix: stagger the pair submission by half a chain, or move
   stage_b of clip 2 to start against stage_a of clip 1 deliberately.
3. **Serial non-block segments** (upsample, separate, noise, refills run
   alone on one card while the other idles) -> fix: prefetch/overlap the
   next clip's stage_a head against the current clip's tail.

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
