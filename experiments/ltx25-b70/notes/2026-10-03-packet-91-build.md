# Packets 91 / 91b: decode capacity on the idle sampler card (2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

**Launch 91b, not 91.** `prepared-encoder-decode-91` (manifest `d566fc1b...`)
stays in place and must not be launched; `run-campaign-91.sh` refuses to start.
A review found these defects in it, all fixed in 91b:

1. **Replica work ran outside `CAPTURE_LOCK`.** Replica kernels and
   allocations on xpu:1 (construction copy, probe decodes, pipelined
   decodes) could overlap a sampler graph capture on xpu:1, which by
   contract must be exclusive.
2. **A failed probe left the replicas resident on xpu:1.** The control arm
   would then have run with less headroom than today.
3. **The copy check missed non-persistent buffers.** It compared
   `state_dict()`, which skips them (e.g. the NA decoder's
   `default_inference_timesteps`), so "every buffer verified" was false.
4. **A queued preview was handed to ComfyUI as a filename.** The token
   `queued:<run>/preview` went to ComfyUI as if it were a saved file.
5. **Placement changes were unguarded.** A replica -> control switch in the
   same index stream could strand a pending clip.
6. **The runner required the timers ON.** This is a speed comparison and the
   timers cost ~12 % per clip, so 91b requires them OFF.

## Why

[f90c](2026-10-03-packet-90c-results.md) ran 117/117 exact. Its busy-window
timers show the two sampler cards are mostly idle: xpu:0 is occupied 40.9 %
and xpu:1 44.8 %, with 1-5 % co-run overlap.

The stream was paced by the decode job, not the sampler:

- Decode median was 1.778 s: VAE + audio 1.630 s, MP4 save 0.145 s.
- Decode runs on xpu:3, which also carries the text-encoder shard.
- Decode alone takes about 0.71 s (f84).
- The sampler could deliver one clip every ~1.39 s.

Packet 91 adds a second decode placement on xpu:1. It does this without
changing any arithmetic, and only after a byte-equality probe on the same
server has passed.

## Design

### Decode placements

Placements are chosen per request by the graph arm. No gate latches when the
mode changes.

| Arm | Decode mode | Placement |
| --- | --- | --- |
| `pipe-samp2-tsh` (control) | `pipeline-save` | Native ComfyUI decode on xpu:3, one worker. Same as 90c, except the preview save moves to the writer thread. |
| `pipe-samp2-tsh-rep` | `pipeline-replica` | Even clip indices decode natively on xpu:3; odd indices decode on an exact VAE replica on xpu:1. Two decode workers, decode depth 2. |
| `pipe-samp2-tsh-mov` | `pipeline-moved` | Every clip on the xpu:1 replica, one at a time. Built but not run by the runner. |

**Emission order.** Clips are emitted strictly in clip order. This is the same
mechanism that keeps the two-clip sampler exact: `run_behind` collects by
index, so out-of-order completion cannot reorder emission. A CPU test proves
this.

**Per-card serialisation.** Each card has its own lock, so neither card ever
runs two decodes at once. When the second worker exists, the control arm still
decodes one clip at a time on xpu:3.

**Worker count.** `ltx_pipeline.set_stage_workers` can only raise the count. The
second worker is created on the first replica request; the control arm runs
before that, with one worker, as in 90c.

### The replica (`ltx_decode_replica.py`)

**Construction.**

- Every parameter, buffer and plain tensor attribute of the resident video and
  audio VAE modules is copied to xpu:1 through host memory, with no peer path.
- `torch.device` attributes that name xpu:3 are repointed to xpu:1.
- The copy is verified byte-for-byte, and no storage is shared with the
  source. Verification covers parameters, all buffers (persistent and
  non-persistent; 91 compared `state_dict()` and missed the non-persistent
  ones) and plain tensor attributes. Receipts report
  `tensors_byte_verified` with that wording.
- Construction runs under the resident fast path's load lock, so ComfyUI
  cannot move the source VAE while it is being copied.

**No model management.** The replica is never registered with ComfyUI model
management. Its `load_models_gpu(memory_required=...)` could evict the 19.3 GB
transformer shard from xpu:1 to make room.

**Decode path.** The replica decode mirrors ComfyUI's non-tiled `VAE.decode`
line for line, plus the reshape/movedim done by `VAEDecode` and
`LTXVAudioVAEDecode`. A test fails if any of the mirrored ComfyUI lines change.

- There is no tiled fallback: an out-of-memory error fails the clip loudly.
- Only batch 1 is admitted.
- Decodes run on a dedicated xpu:1 stream, which is synchronised before
  results are returned.

**Graph capture.** The decode is eager, so there are no capture streams and no
graph pools. The per-thread pool pattern from packet 83 therefore does not
apply. The NA decoder seeds its own per-call device generator with seed 0, so
nothing global is shared between the two decode threads.

**Placement allowlist.** Native is xpu:3, replica is xpu:1, and nothing else
is admitted. The allowlist is checked at build time and on every replica
request. The VAE graph gate is not loosened: it stays in `original` mode in
every packet-91 arm.

### Lock order (91b)

Every eager replica operation on xpu:1 holds `ltx_graph_capture.CAPTURE_LOCK`
in **shared** mode, the mode the sampler's graph replays use. This covers the
construction copy, the probe's replica decodes, every pipelined replica decode
and the post-failure release. A graph capture (exclusive) therefore never
overlaps them, and they never overlap a capture.

Locks are always acquired outer to inner:

```
decode node _REPLICA_LOCK -> CAPTURE_LOCK (shared) -> Replica.lock      (decode, probe, release)
resident fast-path _LOAD_LOCK -> CAPTURE_LOCK (shared)                   (replica construction)
decode node _NATIVE_LOCK -> _LOAD_LOCK (inside ComfyUI VAE.decode)       (native, unchanged)
```

Why this cannot deadlock:

- No code path holds `CAPTURE_LOCK` in either mode while taking
  `_REPLICA_LOCK`, `Replica.lock` or `_LOAD_LOCK`. Graph captures and replays
  only synchronise, fill static buffers and record/replay; I checked the
  sampler blocks and the text-encoder layers.
- The decode threads never capture, so they never ask for the exclusive mode
  while holding the shared one.

The native xpu:3 decode is unchanged from 90c and does not take
`CAPTURE_LOCK`. A CPU test shows that a held capture blocks a replica decode
and the construction copy, and that a running replica decode blocks a capture.

### Cross-card probe (`LTXDecodeReplicaProbe`, graph `graphs/decode-replica-probe.json`)

Inputs: the ten fixtures' certified latents. These come from the first exact
f90c-endure capture of each fixture. Each file's sha256 is pinned in
`probe/decode-replica-fixtures.json`, and its latent sha256s must equal the
reference's.

The probe decodes each fixture on xpu:3 and on xpu:1. It passes only if:

- every image and waveform is byte-identical across the two cards;
- every image and waveform matches the stored reference sha256;
- xpu:1 keeps at least 5 GiB free after the replica is built and at least
  1 GiB free after the probe's decodes.

**Release on failure (91b).** Each replica is registered as soon as it exists.
On any non-pass verdict, the replicas are released:

- Non-pass verdicts are: mismatch, low memory after the build or after the
  probe, and any exception, including one half-way through construction.
- Release drops all references, runs gc, then calls `torch.xpu.empty_cache()`
  on xpu:1 only, under the shared capture lock. That frees unused
  default-pool blocks only; captured graphs' private pools are untouched.
- The receipt records reserved and free memory before and after (`released`)
  and which replicas remain resident (`replicas_resident`). Only a passed
  probe leaves the replicas resident.

Until a probe passes, the replica modes are refused. The refusal writes a
receipt, submits nothing and latches nothing. Replica decodes also require the
same VAE objects the probe qualified.

Outcomes are `replica-exact`, `replica-not-exact` or `insufficient-memory`.
The last two are valid recorded answers. I checked offline that all ten
pinned captures match their references.

### Preview writer

- One writer thread with a bounded FIFO of size 4. When it is full, the decode
  worker blocks, so a preview is never dropped.
- The writer works on private CPU copies of the outputs.
- The guarded save is unchanged: failures go to `save_failures` and are never
  raised.
- Each save records its own time and queue wait, and writes a `save` done
  marker.

**Save record (91b).** A queued preview is recorded as
`status: queued-to-writer` with `saved_file: null` (save record v2) and is
shown to ComfyUI as text, never as a path. The real path appears in that
save's `pipeline-done-save-<index>.json` marker and in a later decode
receipt's `preview_writer.saves`.

### Placement-change guard (91b)

A request whose placement mode differs from the previous one is refused when
the same index stream still has pending decode jobs. "Same stream" means
pending indices within 8 below the new index. The refusal writes a receipt,
submits nothing and latches nothing. Fresh index bases, at least 100 apart in
every campaign, are always admitted.

### Kept from earlier packets

- The three handoff sentries.
- Busy-window timers and the `LTX_BUSY_WINDOWS=0` switch.
- Done markers and the proven-quiescence stop.

Decode jobs now also get busy windows (route `decode`) on the card they run
on, so xpu:3 decode occupancy and the decode share of xpu:1 are measured. Each
window covers the job from first issue to completion, so it is an upper bound.

**Encode-worker busy windows were not added.** The text encoder's graph path
lives in another module; it was not a small change.

## Memory (from f90c receipts)

**xpu:1 today.** The transformer shard is 19.33 GB loaded. Across 120 receipts
the peak was 18.16 GiB allocated and 24.24 GiB reserved. Device total is
32656 MiB (31.89 GiB), so about 7.65 GiB is outside torch's reserve.

**Replica size.** Video VAE 1.472 GB plus audio VAE 0.365 GB, 1.71 GiB in
total. That leaves about 5.9 GiB, less driver overhead.

**Decode working set.** On xpu:3 the resident weights are 12.74 GB
(11.87 GiB). Reserved peaked at 16.64 GiB and allocated at 13.98 GiB. Decode
therefore needs at most about 4.8 GiB, and that bound also includes the text
shard's activations.

**Worst case.** About 1.2 GiB stays free on xpu:1. The probe's thresholds turn
any shortfall into `insufficient-memory` instead of driver paging.

## Packet (91b)

- `R/prepared-encoder-decode-91b`, **manifest sha256
  `c9ed69b73c641817983565dada5fc487bb38a9727fd623d064a721e014d0564e`**.
- Compared with 91: same inventory. Only `ltx_decode_replica.py`,
  `pipeline_decode_node.py` and its node copy differ.
- Compared with 90c:
  - Added: the replica module, two arm graphs, the probe graph and the probe
    fixture list.
  - Changed: `ltx_pipeline.py`, `pipeline_decode_node.py` and its node copy,
    and the launcher checker.
  - Unchanged: everything else, including the control arm's graph.
- No stale pins. Custom-node imports resolve.

Gate (`--check-only`), with server_args elided:

```
gate rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-decode-91b",
  "packet_manifest_sha256": "c9ed69b73c641817983565dada5fc487bb38a9727fd623d064a721e014d0564e",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

## Launch (91b, busy timers OFF)

This is a speed comparison. The busy-window timers cost about 12 % per clip
(90c timed vs control), so the server is launched with `LTX_BUSY_WINDOWS=0`.
The runner refuses to start otherwise. As a result, no occupancy or
decode-route windows are recorded in this run.

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91b
nohup env LTX_BUSY_WINDOWS=0 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 c9ed69b73c641817983565dada5fc487bb38a9727fd623d064a721e014d0564e --run-name encoder-server-decode-91b > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-decode-91b.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-91b.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-91b.log 2>&1 &
```

`run-campaign-91b.sh` uses one server. The index bases 91 reserved
(208089/208189/208289) are burned; 91b uses new ones:

| Step | Prompts | Index base | Client bound | Clips verified |
| --- | --- | --- | --- | --- |
| Warm (`pipe-samp2-tsh`) | 3 | 208489 | 900 s | 0 (all fills) |
| Probe | - | - | 1500 s | 10 fixtures, each decoded on both cards, byte-compared |
| Control (`pipe-samp2-tsh`) | 30 | 208589 | 1800 s | 27 (2 sampler fills + 1 decode fill) |
| Replica (`pipe-samp2-tsh-rep`), only if the probe passed | 120 | 208689 | 3600 s | 116 (2 sampler fills + 2 decode fills) |

- **Tail clips.** The last `depth` clips of each arm are decoded but never
  emitted. This is inherited benchmark behaviour and is not drained.
- **Client bounds.** Every client call runs under `timeout`, which bounds the
  fixtures client's internal GET retries. A timed-out client exits 124, which
  counts as an arm error and leaves the server up.
  `run-throughput-fixtures.py` itself is unchanged.
- **Sync.** After each arm and after every 10 completed replica prompts.
- **Stop.** Only on proven quiescence: a successful, empty queue response and
  a done marker for every submitted sample, decode and save job. Otherwise
  the server stays up and the runner exits non-zero. Exit codes are listed in
  the script.

## What each arm proves, and expected outcomes

- **Probe.** It shows whether xpu:1 decode is byte-identical to xpu:3 and to
  the references, and whether it fits in memory. On any other verdict, the
  replicas are released before the control arm runs (see `released` in the
  receipt), the replica arm is skipped, and the control still runs.
- **Control (30).** The interval baseline on this server, with timers off and
  the preview save off the decode worker. Expect a median near f90c control's
  1.58 s, paced by decode on xpu:3.
- **Replica (120).** Exactness comes from the run's own oracle over 116
  clips. If xpu:1 decode costs about what xpu:3 decode does and does not slow
  the sampler much, the pace should fall toward the sampler's ~1.39 s per
  clip. xpu:1 is single-CCS, so decode competes with sampler replays there;
  watch the sampler job time and the per-slot decode rows.
- **Reading the results:**

  ```
  analyze-phases.py R/encoder-server-decode-91b f91b-rep
  analyze-phases.py R/encoder-server-decode-91b f91b-ctl
  ```

  Look at the per-slot decode time, lock wait, writer save time and queue
  wait. Occupancy is absent because the timers are off.

## Unverified offline

- Whether xpu:1 decode is byte-identical. The probe decides; nothing offline
  can.
- Whether deep-copying the real VAE modules works: whether every tensor is
  caught, and whether there is hidden device state that is not a
  tensor/device attribute. Construction fails closed if any tensor stays off
  xpu:1, but non-tensor state would only show up as a probe mismatch or a
  runtime error.
- The true decode working set on xpu:1, and whether sharing xpu:1 slows the
  sampler.
- Real-runtime behaviour of the second decode worker under GIL contention.
- Whether `torch.xpu.mem_get_info` exists in this torch build. If not, the
  code falls back to total minus reserved, which ignores driver overhead.
- How much the shared `CAPTURE_LOCK` costs. A replica decode holds it for
  about a second, and sampler captures happen only at warm-up or for new
  signatures. A capture waits for a running replica decode, and a replica
  decode waits for a running capture.
- Whether `empty_cache` on release returns the replica memory in practice.
  The receipt records it.
- The negative-tamper tests were not run, because they write scratch packets
  into R.
