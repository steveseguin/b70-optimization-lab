# Packet 90b: busy windows + decode split on the sentry build (2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

## Why

f90 (the sentry build) ran without the packet-90 timers, which sat unmerged
on `origin/packet-90`. Two questions are still open
([salvage](2026-10-03-packet90-salvage.md)): where the ~0.7 s/pair packing
loss goes ([design](packet-90-packing-loss-design.md)), and how the 1.60 s
decode job splits between VAE decode and the MP4 preview save
([capacity budget](2026-09-21-capacity-budget-24fps.md)).

## What the packet contains

`R/prepared-encoder-busy-90b`, built by `scripts/prepare-graph-capture-runtime.py`
(only its OUTPUT literal changed). The parent is packet13, as for every
graph-capture packet. Compared with `prepared-encoder-sentry-90`, the file
inventory and graphs are identical. Five files differ: `ltx_graph_capture.py`,
`pipeline_sampler_node.py` and `pipeline_decode_node.py`, plus the
custom-node copies of the last two. The other fields that differ are their
`extension_sha256s` and graph-capture digests, and `preparer_sha256`.

- **Manifest sha256 `ab45830c64ed163044e64c2edf4cf835af58aaa14a1e25ed317211b192c8f749`**
- All three handoff sentries from packet 90 are unchanged.
- **Busy windows** (cherry-picked from 6296a0e20, then fixed). Each graph
  replay in `GraphBlockRoute._call_native` is bracketed by a pair of timing
  events. Each device also gets one anchor event, so the report can place
  every window on that card's timeline. Sampler receipts gain
  `route_busy_ms`, which holds:
  - `<dev>/route<i>`: `{count, ms}`
  - `_devices.<dev>`: `{windows, sum_ms, union_ms, span_ms}`
  - `_meta`: `{carried, dropped, errors, unplaced}`, when any are nonzero
- **Decode split** (cherry-picked from 99f4940fe, then fixed). Decode
  receipts gain `detail.decode_split = {vae_s, save_s}`. This is the split
  of the clip the receipt emits, recorded by that clip's own job.
- Sampler and decode receipts gain `written_unix`, the wall time when the
  receipt was written.

Fixes to the picked code, none of which had ever run:

- `busy_window_report` was missing `global`, so it raised UnboundLocalError
  on its first call.
- The events were created without `enable_timing`, so every window would
  have failed to time and gone to an unbounded pending list.
- The decode split was attached to the wrong clip. The current clip's
  still-running dict was written into the emitted clip's receipt.

All of these changes only read clocks and events. Grep for pins before the
build: no file pins the three changed modules. `AV_SOURCE_SHA256` and
`SHARD_SOURCE_SHA256` still match `av_model.py` and `ltx_layer_shard.py`. No
64-hex literal in the packet names a replaced file. Every custom-node import
resolves, including function-level imports, and each node copy is
byte-identical to its helper.

## Gate (`--check-only`, 2026-10-03 15:2x EDT; server_args elided)

```
rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-busy-90b",
  "packet_manifest_sha256": "ab45830c64ed163044e64c2edf4cf835af58aaa14a1e25ed317211b192c8f749",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

Check-only does not run the launch-time gates: the kernel-journal fault
regex, render-device ownership and locks. Running the launcher's FAULT regex
offline against `journalctl -k -b` for boot 37491ca5 found 0 matches. The
launcher requires MemAvailable >= 16 GiB, which was 18.5 GiB at gate time,
while a memtest held about 104 GB. Do not launch until the memtest has ended.

## Launch (server first, then runner)

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-busy-90b
nohup /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P \
  --manifest-sha256 ab45830c64ed163044e64c2edf4cf835af58aaa14a1e25ed317211b192c8f749 \
  --run-name encoder-server-busy-90b \
  > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-busy-90b.log 2>&1 &

nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-90b.sh \
  > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-90b.log 2>&1 &
```

`run-campaign-90b.sh` runs these steps:

1. Checks the manifest pin, runs the runtime-PM check, then waits for
   server health.
2. Verifies that the server identity is this packet and the pid/ticks.
3. Rests 60 s.
4. Runs `f90b-warm` (3 prompts, index base **204989**), then `sync`.
5. Settles 60 s.
6. Runs `f90b-endure` (120 prompts over the ten fixtures, index base
   **205089**), with `sync` every 10 completed prompts and after the arm.
7. Stops gracefully: waits for an empty queue, drains 60 s, sends one
   SIGINT to the verified launcher pid, waits up to 180 s and never
   escalates.

The stop is skipped if FAULT.json is latched or the endure arm ends in an
execution error or timeout. The server is then left up for review.

Index bases: the highest clip index any run had used is 203193
(sentry-90), and the load probes used 210000. Receipts are committed but
not pushed. Never kill the server child directly. Once the runner has
started, do not edit the script.

## Expected outcomes and how to read them

```
scripts/analyze-phases.py R/encoder-server-busy-90b f90b-endure
```

The analyzer recovers the index base itself. Steady state means
emitted - base >= 2.

- **Exactness / sentries.** Read these as for f90. Expect 120/120 exact or
  a sentry latch that localizes the wrong clip (outcome table in the
  [sentry note](2026-09-21-packet90-handoff-sentries.md)).
- **Timer overhead.** Compare the runner's `steady_mean_s` with f90's
  1.597 s median interval. A rise of more than about 3% means the extra
  event records cost real time, since the sampler is dispatch-bound. In
  that case, read the busy shares as relative, not absolute.
- **Occupancy (`route_busy_ms` table).** `occupancy` is union / wall: the
  card time with any replay in flight. `co-run overlap` is the share of
  window time during which both threads had a replay on the card.
  - Both cards well below 100% union: the loss is idle card time, i.e.
    host stalls or serial non-block segments (design-note causes 1 and 3).
  - Unions near 100% with large overlap: the loss is co-run inefficiency
    (cause 2).
  - Compare the per-card medians of `union/rcpt` with the design note's
    demand of 2.38 s (xpu:0) and 2.66 s (xpu:1) per pair.
  - `unplaced > 0` means XPU refused cross-stream elapsed_time. Only the
    summed figures are then valid, and `occ(sum)` can exceed 100%.
- **Decode split.** If `save` is a large share of the 1.60 s job, moving
  the MP4 save off the decode worker is the decode-side lever. If `vae`
  dominates, decode stays co-limiting.

## Not verified offline

- The XPU event behaviour on the real runtime: `query()`, cross-stream
  `elapsed_time` against the anchor, and the cost of about two event
  records per block replay.
- Whether the graceful SIGINT stop exits cleanly with idle pipeline worker
  threads.
- The negative-tamper tests (`test-graph-capture-packet-negative*.py`)
  were not run. They write scratch packets into R. The checker and
  launcher are byte-identical to packet 90's.
