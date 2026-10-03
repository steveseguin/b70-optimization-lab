# Packet 91: decode capacity on the idle sampler card (2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

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
  source.
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

## Packet

- `R/prepared-encoder-decode-91`, **manifest sha256
  `d566fc1b5fa80b75dcb259d63e8aaabbffa2911cf84fb6817254a645d1673147`**.
- Compared with 90c:
  - Added: the replica module, two arm graphs, the probe graph and the probe
    fixture list.
  - Changed: `ltx_pipeline.py`, `pipeline_decode_node.py` and its node copy,
    and the launcher checker.
  - Unchanged: every other file, including the control arm's graph.
- No stale pins. Custom-node imports resolve.

Gate (`--check-only`), with server_args elided:

```
gate rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-decode-91",
  "packet_manifest_sha256": "d566fc1b5fa80b75dcb259d63e8aaabbffa2911cf84fb6817254a645d1673147",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

## Launch

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91
nohup /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 d566fc1b5fa80b75dcb259d63e8aaabbffa2911cf84fb6817254a645d1673147 --run-name encoder-server-decode-91 > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-decode-91.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-91.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-91.log 2>&1 &
```

`run-campaign-91.sh` uses one server with the timers on:

1. Warm: 3 prompts @208089.
2. Probe.
3. Control: 30 prompts @208189.
4. Replica: 120 prompts @208289, only if the probe passed.

The runner syncs after each arm and every 10 replica prompts. It stops the
server only on proven quiescence: the queue must be empty and every sample,
decode and save job must have its done marker. Exit codes are listed in the
script.

The timers cost about 12 % in the 90c control comparison. Compare the arms of
this run with each other, not with the timers-off f90c control.

## What each arm proves, and expected outcomes

- **Probe.** It shows whether decode on xpu:1 is byte-identical to xpu:3 and
  to the references, and whether it fits in memory. If it fails, the packet's
  answer is "replica not exact" (or "no room"). The runner skips the replica
  arm and still runs the control.
- **Control (30).** This is the interval baseline on this server, with the
  preview save moved off the decode worker. Expect a median of roughly
  1.6-1.8 s with timers on, paced by decode on xpu:3.
- **Replica (120).** Exactness comes from the run's own oracle: 116 distinct
  clips are expected, since decode depth 2 makes prompts 0-3 fills (the
  control's 30 prompts give 27).
  - If xpu:1 decode costs about what xpu:3 decode does and does not slow the
    sampler much, the pace should fall toward the sampler's ~1.39 s per clip.
  - xpu:1 is a single-CCS card that is 55 % idle, so decode competes with
    sampler replays there. Watch xpu:1 occupancy, the sampler job time and
    the `vae decode replica` / `vae decode native` rows.
- **Reading the results:**

  ```
  analyze-phases.py R/encoder-server-decode-91 f91-rep
  analyze-phases.py R/encoder-server-decode-91 f91-ctl
  ```

  Look at per-slot decode time, lock wait, writer save time, the `decode`
  route windows, and per-card occupancy.

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
- The negative-tamper tests were not run, because they write scratch packets
  into R.
