# Packet 77 results (2026-09-18 04:13-04:23 UTC, boot on kernel 7.0.0-30, GuC 70.44.1)

Server `encoder-server-graph-capture-77`, one server for the campaign, no faults,
no freeze during the run. Ten distinct prompt/seed fixtures, per-clip
four-tensor oracles, intervals between distinct emitted clips (fills excluded).

| Arm | Prompts | Distinct | Exact | Mean s | p95 s | min s | fps equiv |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pipe-samp2-tsh` (f77-tsh) | 30 | 27 | 27/27 | **1.515** | 2.863 | 1.129 | 16.5 |
| `pipe-samp2` control (f77-samp2) | 24 | 21 | 21/21 | 1.667 | 2.807 | 1.149 | 15.0 |
| `pipe-samp2-tsh` endurance (f77-endure) | 120 | 117 | 117/117 | 1.639 | 2.900 | 1.161 | 15.3 |

## What happened

1. **The encoder shard never installed.** The runner's warm clip ran the plain
   pipe graph, whose text gate mode is `graph`; that placed the whole 25 GB
   encoder on xpu:2 and installed the plain graph shadows. The later
   `graph-shard` request found the gate already installed and recorded
   `installed_now: false` (the receipt's `text_shard` is absent; xpu:3 holds
   only the VAEs, 1.8-3.2 GiB). Per-clip encode time stayed 1.59-1.83 s.
   Only the gate's side effect took: two encode workers, both on xpu:2.
2. **Two encodes on one card still overlap.** The encoder is partly
   dispatch-bound, so two in flight gave a run of intervals at 1.13-1.27 s
   (the sampler-bound regime) interleaved with 1.59 s encoder-bound
   intervals and periodic 2.8-3.2 s spikes. Interval histogram, tsh arm:
   11 under 1.3 s, 12 in 1.3-1.7 s, 3 over 1.7 s.
3. **Load lock proven.** 120 prompts through the two-clip sampler with no
   segfault (server 74b died on prompt 4 of the same stream).
4. **Control regressed 1.607 -> 1.667 s** versus packet 74 on the old
   kernel/firmware; within the spike-driven noise (p95 2.8 s in both), but
   not dismissed: the `pipe-samp2` arm now runs after the shard gate set
   `STAGE_WORKERS['encode']=2`, which the control's `original` text mode does
   not reset.
5. **Memory (endurance clip 99, reserved/allocated GiB):** xpu:0 28.7/20.9,
   xpu:1 29.2/19.6, xpu:2 28.5/27.2, xpu:3 3.2/1.7. The 23/25 transformer
   split (+1.55 GB on xpu:0) would leave about 1 GiB; not safe as is.

## Spikes

Every arm shows 2.8-3.2 s intervals every 7-10 clips, in packet 74 as well.
Candidates: the save-behind MP4 write, encode-ahead speculation, allocator
pool growth. The pipeline receipts' wait column ramps 0.04 -> 1.5 s over
each cycle and resets at the spike. Unattributed; next receipt to add is a
per-stage timestamp trace per clip.

## Decision

Sharded encoder unmeasured; runner 77b puts the warm clip on the sharded
graph itself so the shard installs before the first placement. Same packet,
fresh index bases, one controlled reload (also the first teardown transition
on the new kernel/firmware with the hard-lockup panic armed).
