# Packet 114 launch procedure (for the coordinator; the authoring agent never launches)

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114` |
| Manifest SHA-256 | `3e8b7abeb21fff903869907fd67c41128dd6179fa17fa441abdd5544468c97f3` |
| Payload | 113,443,722 bytes (`du -sb`; 113 was 112,614,223) |
| Parent | packet 113, manifest `a23dbc94…f7f28b` (verified at load and at launch, with 112 and 111 behind it) |
| Plan | `e87c6214…49b5b`; 8 qualification ids (frames/placement/anchor), 16 graph pins per qualification row |
| Build receipt | `data/resume-20261008/continuation114-build.json` |
| Unit | `ltx114-stream-server-20261008` |
| Client | `stream/ltx_continuation_client.py --packet 114` |

## 0. What is different from 113, operationally

- **Latent anchor by default** (`LTX_ANCHOR=latent`); `LTX_ANCHOR=frame` is
  113's decoded-frame anchor for the A/B. **The latent anchor changes the
  output**: the owner decides it after the side-by-side (§7).
- **The decode runs on one ordered thread** on xpu:3, behind the chain. Receipt
  first, then `receipts/decode-<run>.json`, then the MP4 and
  `receipts/preview-<run>.json`.
- **Chunk length at launch:** `LTX_STREAM_FRAMES=97` (preferred) or `49`.
- **Text reuse on** (`LTX_STREAM_TEXT_REUSE=1`).
- **Names:** everything the server creates outside its run directory is
  `stream114-…`. The launcher refuses to start if any 114 setup/qualification
  name or any `stream114-` entry exists under `output/`, `output/validation/` or
  `requests/` — also in `--check-only`. After a failed 114 launch, archive those
  folders before the next launch.
- Same model files as 113 (sampler, decoder, conditioning node, text encoder,
  upsampler: byte-for-byte), same floors (8/8/2/9 GiB before each chunk, 2 GiB
  after), same latches. New: a 9 GiB xpu:3 floor checked before every decode.
- **Not in 114:** overlapping chunk N+1's stage A with chunk N's stage B (packet
  115), encode-ahead (115), decoder capture.

## 1. Fresh admission (immediately before launch)

1. **Stop the running 113 server by the controlled single reload** (an
   application reload, not a host restart), once its measurement is done:

   ```
   systemctl --user stop ltx113-stream-server-20261008     # one SIGINT (KillSignal=SIGINT, no SIGKILL)
   ```

   Stop its stream client first. Wait for the unit to be inactive; nothing may own
   port 8188, the GPU locks or the render nodes (the launcher checks). No retry,
   no restart loop. **Keep the five-minute gap between the stop and the launch.**
2. **Health receipt:** the four-card postflight probe
   (`scripts/check-four-card-health.py`), same boot, under 6 hours old. Do not poll
   xpu-smi while a server is initialising.
3. **Storage** (the launcher repeats it):

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-114-latent-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   Must report `admitted: true`. At build time (2026-10-08 14:25 UTC):
   120,829,009,920 bytes available against 56,908,316,672 required, so
   117,607,784,448 bytes would remain after the 3 GiB allowance (the parallel
   reclaim had finished; the margin is about 59 GiB).
4. **Names:** `ls /mnt/fast-ai/bench-results/ltx25-baseline-20260913/output | grep stream114`
   and the same for `output/validation` and `requests` must print nothing. On
   2026-10-08 they were clean (CPU test `test_live_root_is_clean_now`).
5. **No `__pycache__`** in the packet (0 after the build and after the
   `--check-only` runs). Every Python command here uses `-B`.
6. **Rehearsal** (optional, passed on 2026-10-08 for 97/latent, 49/latent,
   49/frame, 97/frame on two-way20-28 with `postflight-stream113c.json`): the launch
   command below with `--check-only`, run directly with the venv Python (not
   through systemd-run). It does no device, lock or port work.

## 2. Launch command (97 frames, latent anchor)

Run name `encoder-server-continuation-stream-114-latent-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97`.

```
systemd-run --user --unit=ltx114-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_ANCHOR=latent LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 \
  LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 \
  LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=97 LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114 \
  --manifest-sha256 3e8b7abeb21fff903869907fd67c41128dd6179fa17fa441abdd5544468c97f3 \
  --run-name encoder-server-continuation-stream-114-latent-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
  --health-receipt <fresh four-card health receipt>
```

**At 49 frames:** `LTX_STREAM_FRAMES=49` and run name
`encoder-server-continuation-stream-114-latent-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49`.
**Frame anchor (A/B):** `LTX_ANCHOR=frame` and `…-114-frame-two-way20-28-…-f49`
(or `-f97`). The run name must match the environment
(`<frames>/<placement>/<anchor>`); the launcher refuses any deviation from the
fixed environment.

## 3. Health and identity after start

`GET http://127.0.0.1:8188/ltx-stream/status` returns 200 with:
`phase: "stream_setup"`, `halted: null`, `fault: false`, `packet: 114`,
`anchor: "latent"`, `frames: 97`, `placement: "two-way20-28"`, `text_reuse: 1`,
`features` all true (`latent_anchor` false on a frame launch),
`decode_worker.failed: null`, `preview_writer.failed: null`, and
`runtime_manifest_sha256` equal to the manifest above. The run directory holds
`server-identity.json`, `stream-executor-guard.json`, `health-receipt.json` and
`journal-admitted-faults.txt`; after `stream114-prepare`, also
`stream-preparation.json` (with `registry_lock`) and `stream-native-binding.json`.

## 4. Memory (estimates; the floors are the stop rule)

| card | holds | 113 measured (49 f) | 114 at 97 frames (estimate) | floor |
|---|---|---|---|---|
| xpu:0 | sampler blocks 0–19, upsampler, graph pool | 9.57 GiB free before a chunk | 8.9–9.4 GiB: stage-B tokens 448 → 832 (activations tens of MB); graph pool about 0.7–1.0 GiB, replacing the 49-frame pool | 8 GiB |
| xpu:1 | sampler blocks 20–47, graph pool | 10.1 GiB free | 9.4–9.9 GiB | 8 GiB |
| xpu:2 | text encoder primary shard | unchanged | unchanged | 2 GiB |
| xpu:3 | text secondary shard, video and audio VAE | 14.74 GiB free before a chunk, 13.08 GiB after the decode peak (1.66 GiB) | decode peak about 3.3 GiB (scales with T), so about 11.4 GiB free once the allocator holds it; the decode now also overlaps the next chunk's text-shard work | 9 GiB, now also before every decode |
| host RAM | | | decode thread holds one chunk's images (76 MB at 97); preview writer at most 3 private copies (≈ 240 MB); decode queue latents only (KB) | 16 GiB `MemAvailable` at launch |

xpu:0 is the tight card at 97 frames (margin about 1 GiB over the 8 GiB floor,
estimate). A floor refusal latches with the snapshot in the receipt chain; it
does not corrupt anything. If it trips, relaunch at 49 frames (the length is a
launch option) rather than lowering a floor.

Storage per run: 9 captures × 78,301,440 payload bytes at 97 frames (705 MB; 356 MB at
49), plus per chunk a receipt, a decode record, a preview record (a few KB
each), the MP4, and the two newest 40,960-byte anchors.

## 5. Qualification (11 requests and one verdict action)

Either the stream client runs it (it does by default):

```
/home/steve/.venvs/ltx25-baseline/bin/python -B /home/steve/llm-optimizations/experiments/ltx25-b70/stream/ltx_continuation_client.py \
  --packet 114 --work-dir <client work dir> --poll 0.05 [the lane's usual client options]
```

or the packet's driver does:

```
/home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114/resolution/components/qualify_client.py \
  --frames 97 --anchor latent --placement two-way20-28 --text-reuse 1 \
  --log /home/steve/llm-optimizations/experiments/ltx25-b70/data/resume-20261008/continuation114-qualify.jsonl
```

Order: `stream114-window-probe`, `stream114-prepare`, then eager chain
`stream114-qeager-c00000{0,1,2}`, graph chain `stream114-qgraph-…`, repeat
chain `stream114-qrepeat-…`, then `action:qualify-verdict`. Chunk 0 of each chain
is unanchored; chunk 1 repeats the prompt (text reuse on the graph and repeat
chains); chunk 2 is a cut. The decode thread is drained before every eager and
graph request (they may capture graphs). The repeat chain is the streaming form
and its decodes overlap the next chunk.

**What pass looks like:**

- The verdict returns `passed: true`; `stream-qualification-verdict.json` has
  `exact_replay[k].all_identical` true for k = 0, 1, 2. That means byte-identical
  `video_latent`, `audio_latent`, `stage_a_latent`, `anchor_file`, `images` and
  `waveform` across the three chains.
- Captures agree with the output node and the decode thread. Decode records are
  in order (`sequence` 1…9).
- `decode_overlap` shows `drained: true` on the six gated requests. It should show
  `pending > 0` on at least one repeat chunk. That is the overlap evidence: it
  shows the decode really ran beside the chain.
- The eager chain has zero routes. Graph chunk 0 captured; graph chunk 2 and the
  repeat chain captured nothing; signatures 1–8 per route.
- `stream-geometry-measured.json` exists with `matches: true` and, at 97, audio
  latent `[1,8,101,16]` and waveform `[1,2,192480]`. If the derived 97-frame audio
  shapes are wrong, the first eager chunk writes
  `stream-geometry-mismatch-stream114-qeager-c000000.json` with the measured
  shapes and latches. Report the shapes; the fix is a rebuild with the measured
  numbers, not a retry.
- `slot0_pin` in the anchored receipts: expect `bytes_equal: true`, or
  `differing_all_signed_zero: true` (−0.0 → +0.0 through the sampler blend). This
  is a diagnostic, not part of the verdict.
- Cross-check against 113 (49 frames only, recommended for the first 114
  launch). Compare `stream114-qeager-c000000` with
  `reference-113-qualification-hashes.json` → `stream112-qeager-c000000`. The
  images, video latent, audio latent and waveform must be byte-identical, because
  chunk 0 is unanchored and the decode is the same computation on another thread.
  With `LTX_ANCHOR=frame`, chunks 1 and 2 must match 113 too. A mismatch is a
  finding to report, even if the 114 verdict passed.

Any failure latches; no retry.

## 6. Streaming and what to watch

The client follows CONTRACT.md with `--packet 114` (default `--save-wait` 30 s).
Per chunk, the chain's lag is the receipt's `timing_s.submit_to_anchor_ready`, and
the period is receipt-to-receipt. The decode lag is
`timing_s.anchor_ready_to_decode_done` in `receipts/decode-<run>.json`.

Predictions (medians of 100 stream chunks; each is falsified outside its range):

| launch | start-to-start period | other |
|---|---|---|
| 49, latent | 3.2–3.8 s | sampler-A bucket (`timing_s.sampler_a_bucket`) ≤ 1.65 s |
| 97, latent | 3.6–4.8 s (≤ 1.2 s of work per second of video) | decode record ≤ 2.5 s after `anchor_ready` |
| any, latent | | sampler-A and sampler-B buckets with `decode_at_start.pending > 0` at most 10% above the drained qualification chunks; more means GIL contention |
| 49, frame | about 113's period (4.4–4.7 s) | decode in the chain: `timing_s.decode_in_chain` ≈ 0.95 s |

Also watch:

- `decode_worker.pending` in the status should stay at 0–1. It reaches 3 only
  under back-pressure, which holds the stream; it never drops a chunk.
- `timing_s.sampler_a_split` splits the old 1.61 s bucket. It shows how much of it
  is the upsampler, the stage-B condition and the AV concat.

Stop rules:

- Any eager/replay difference latches, with no retry.
- A floor refusal or a decode/preview failure latches.
- A GPU fault halts new requests; one controlled stop is the single incident
  action. No restart loop and no reboot.
- To stop: one SIGINT (`systemctl --user stop ltx114-stream-server-20261008`),
  then the usual postflight. A decode or preview queued at that moment may be left
  without its record.

## 7. Owner view: frame anchor vs latent anchor seams

The owner decides L1 (latent) against the pixel/frame anchor (and L2, not built)
by looking. Use the same ten kitten prompts and seeds in each run
(`data/stream/kittens-01.json`, `--base-seed` fixed). Use twenty stream chunks
each:

1. 114 at 49 frames, `LTX_ANCHOR=frame` (pixel anchor; 113 run01's 49-frame
   output can stand in if the prompts and seeds match).
2. 114 at 49 frames, `LTX_ANCHOR=latent`.
3. 114 at 97 frames, `LTX_ANCHOR=latent`.

Each is its own launch, with a five-minute gap and a fresh health receipt. Archive
`output/stream114-*` and `output/validation/stream114-*` between launches,
because the naming preflight refuses otherwise.

Then, CPU only, on the finished run directories:

```
python3 -B /home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream/owner_seam_view.py \
  --left  <run dir of 114 frame f49> \
  --right <run dir of 114 latent f49> \
  --out   /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/owner-view-114-frame-vs-latent-f49 --seams 19
```

It writes:
- `seam-NN.mp4`: the last second of chunk n and the first second of chunk n+1,
  after the dropped overlap frame, left = frame anchor, right = latent anchor.
- `stream-side-by-side.mp4`: the whole joined stream.
- `index.json`: per-seam border-to-centre chroma ratios. A ratio that stays flat
  under the latent anchor would support the hypothesis that the halo comes from
  the decode→encode round trip.

Repeat with `--right <114 latent f97>` for the 97-frame view.

The script checks every MP4 against its preview record. It only reads finished
runs and calls ffmpeg; it never talks to a server.
