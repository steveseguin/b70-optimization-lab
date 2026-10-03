# Packet 90c: busy windows + decode split on the sentry build (2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

## Status of 90b: superseded, never launched

`R/prepared-encoder-busy-90b` (manifest `ab45830c...`) stays in place and
must not be launched. `run-campaign-90b.sh` now refuses to start. An
independent review found four defects in it, all fixed in 90c:

1. **The stop could fire without proof that the server was idle.** A failed
   queue request or an exhausted poll counted as quiescence. An empty
   ComfyUI queue does not show that the pipeline workers are idle. A failed
   stop still let the campaign exit 0.
2. **Timing could fail a clip.** Timing exceptions in the replay path were
   unguarded. They would become worker errors, latch the sampler `_failed`
   and clear queued jobs.
3. **Occupancy was wrong across drains.** Each drain unioned only its own
   windows and the analyzer summed those unions, so a carried window
   double-counted overlap. The denominator came from receipt write times.
4. **The analyzer misreported short or degraded runs.** It fell back to all
   rows when no row was steady, and it silently dropped receipts with
   unavailable timing.

## Why

f90 ran without the timers. Two questions are still open
([salvage](2026-10-03-packet90-salvage.md)):

- **Packing loss:** where the ~0.7 s/pair goes
  ([design](packet-90-packing-loss-design.md)).
- **Decode split:** how the 1.60 s decode job divides between VAE decode
  and the MP4 save.

## What the packet contains

- **Packet:** `R/prepared-encoder-busy-90c`.
- **Manifest sha256:** **`80559bde4971229ab0a2ce927ab412ae1a2ca5fde5494abdef5f1da801a22be7`**
- **Built by:** `scripts/prepare-graph-capture-runtime.py`; only its OUTPUT
  literal changed.
- **Difference from `prepared-encoder-sentry-90`:** same inventory and
  graphs. Five files differ: `ltx_graph_capture.py`,
  `pipeline_sampler_node.py`, `pipeline_decode_node.py`, and the two node
  copies.
- **Pins and imports:** no stale pins (`AV_SOURCE_SHA256` and
  `SHARD_SOURCE_SHA256` unchanged). All custom-node imports resolve.
- **Sentries:** the three packet-90 handoff sentries are unchanged.

### Busy windows (sampler receipts, `route_busy_ms`)

- Event markers bracket each graph replay. One anchor event per card gives
  that card a clock.
- Each drain emits:
  - `<dev>/route<i>`: `{count, ms}`.
  - `_devices.<dev>`: `{windows, sum_ms, segments, coalesced_gap_ms}`.
    The segments are the merged busy intervals of that drain on the card
    clock, at most 2048. If more, the smallest gaps are coalesced, and the
    largest gap closed is recorded.
  - `_meta`: carried, dropped, errors and unplaced counts, plus `disabled`.
- **Guard:** `busy_begin`/`busy_end` never raise. The first exception
  disables the timers for the process and records its text once in
  `_meta.disabled`.
- **Replay ordering:** `entry.graph.replay()` is unconditional and stays
  between the markers. A failure only removes markers.
- **Switch:** **`LTX_BUSY_WINDOWS=0`** in the server environment turns the
  timers off entirely; no event is created. The sentries stay on.

### Decode split

- Decode receipts carry `detail.decode_split = {vae_s, save_s}` for the
  clip they emit. Every timing step is wrapped so it cannot fail a clip.

### Done markers

- The sampler and decode workers write
  `RUN/pipeline-done-{sample,decode}-<index>.json` once a job's GPU work has
  finished. Writing a marker never raises.
- The runner uses these markers as positive proof that the pipeline is
  idle before it stops the server.

### Exactness is unproven

No tensor, RNG, stream or device assignment changes. However, the extra
event commands and the lock can change how the two sampler threads
interleave their submissions. **Byte-identity of 90c is unproven until the
run's own oracle comparison.** The control arm separates timer effects:
same packet, timers off.

## Gate (`--check-only`, 2026-10-03; server_args elided)

```
gate rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-busy-90c",
  "packet_manifest_sha256": "80559bde4971229ab0a2ce927ab412ae1a2ca5fde5494abdef5f1da801a22be7",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

- The gate also passes (rc 0) for run name `encoder-server-busy-90c-ctl`.
- Not exercised by check-only: the launch-time journal fault regex, render
  ownership and locks.
- I scanned the current boot's kernel log offline for the fault keywords:
  0 matches.
- MemAvailable was 18.5 GiB against the launcher's 16 GiB minimum. Do not
  launch while the memtest is running.

## Launch

Timed run (server first, then runner):

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-busy-90c
nohup /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 80559bde4971229ab0a2ce927ab412ae1a2ca5fde5494abdef5f1da801a22be7 --run-name encoder-server-busy-90c > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-busy-90c.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-90c.sh timed > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-90c.log 2>&1 &
```

Control run, on a later fresh server after the timed one has stopped:

- Prefix the server command with `env LTX_BUSY_WINDOWS=0`.
- Use `--run-name encoder-server-busy-90c-ctl`.
- Start the runner as `run-campaign-90c.sh control`.

The runner refuses to start if the server's environment does not match the
mode.

### Index bases

| Mode | Warm | Endure |
| --- | --- | --- |
| timed | 206989 | 207089 |
| control | 207389 | 207489 |

Indices already used elsewhere: up to 203193 by earlier runs, 204989/205089
reserved by the unlaunched 90b runner, and 210000 by the probes.

### What the runner does

- **Arms:** same shape as f90. Health wait, identity check of
  pid/ticks/manifest/env, 60 s rest, 3-prompt warm, 60 s settle, 120-prompt
  endure.
- **Sync:** after each arm and every 10 completed endure prompts.
- **Commits:** receipts are committed, not pushed.
- **Stop:** the runner stops the server only after proving both of these:
  - a queue request **succeeds** and shows nothing running or pending;
  - every sample job (base+i) and decode job (base+i-2, i >= 2) of both
    arms has its done marker.

  It then sends one SIGINT to the verified launcher pid and waits up to
  180 s, never escalating.
- **Otherwise:** the server is left up and the runner exits non-zero.

Exit codes:

| Code | Meaning | Server |
| --- | --- | --- |
| 0 | all good | stopped |
| 3 | oracle mismatch | stopped |
| 1/2 | arm error or timeout | up |
| 4 | FAULT latched | up |
| 5 | queue not provably empty | up |
| 6 | job markers missing | up |
| 7 | stop failed | still running |
| 8 | refused before running | not touched |

## Reading the results

```
scripts/analyze-phases.py R/encoder-server-busy-90c f90c-endure
```

- **Steady rows:** emitted - base >= 2. If no row qualifies, the analyzer
  prints `NO STEADY ROWS` and exits 2.
- **Exactness/sentries:** read as for f90 (outcome table in the
  [sentry note](2026-09-21-packet90-handoff-sentries.md)). This is also the
  identity proof for 90c.
- **Timer cost:** compare `steady_mean_s` against the control arm. f90's
  median interval was 1.597 s.
- **Occupancy:**
  - Segments are merged across all steady receipts on each card's clock.
  - occupancy = union / (first start to last end).
  - co-run overlap = (summed - union) / summed.
  - Every line carries `[timing unavailable in k/n steady receipts]`.
- **How to read the cards:**
  - Both cards well below 100% means idle time: host stalls or serial
    segments (causes 1 and 3).
  - Near 100% with large overlap means co-run inefficiency (cause 2).
  - Compare union per pair against the demand estimates: 2.38 s for xpu:0
    and 2.66 s for xpu:1.
- **Decode split:** a large `save` share points to moving the save off the
  decode worker. If `vae` dominates, decode stays co-limiting.

## Not verified offline

- **XPU events on the real runtime:** `query()`, cross-stream
  `elapsed_time` to the anchor (if refused, `unplaced` > 0 and occupancy is
  n/a), and the cost of the markers.
- **SIGINT exit:** whether it is clean with idle worker threads.
- **Interleaving:** whether the timers change thread interleaving.
- **Phase marks:** the pre-existing phase marks (packet 89 onward) still
  read events unguarded. They ran cleanly through f89/f90 and are unchanged.
- **Negative-tamper tests:** `test-graph-capture-packet-negative*.py` was
  not run because it writes scratch packets into R. The launcher and
  checker are byte-identical to packet 90's.
