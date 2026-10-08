# Packet 116 launch procedure (for the coordinator; the authoring agent never launches)

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116` |
| Manifest SHA-256 | `6bced5b4e9ad7b1c69d530c172244f24414fdd4b270d0fa8ba9302d8d047c2db` |
| Payload | 115,647,911 bytes (`du -sb`; 115 was 114,467,679) |
| Parent | packet 115, manifest `a934bac2…4c7137` (verified at load and at launch, with 114, 113, 112 and 111 behind it) |
| Plan | `af735204…829a98`; 32 qualification ids (frames/placement/anchor/decoder graph), 64 graph pins per qualification row |
| Build receipt | `data/resume-20261008/continuation116-build.json` |
| Unit | `ltx116-stream-server-20261008` |
| Client | `stream/ltx_continuation_client.py --packet 116 --expect-anchor frame --expect-decoder-graph 1` |

## 0. What is different from 115, operationally

- **Default anchor `frame`** (113 semantics at both stages; sharp seams). `mixed`, `latent`, `guide` kept.
- **116a scheduling** (frame): the chain waits only for the video decode and the anchor file; the audio
  decode, hashes, diagnostics, decode record and MP4 run on the decode thread while the next chunk runs.
  Eager and graph qualification chunks wait for their whole decode (every mode).
- **`LTX_DECODER_GRAPH` (must be set explicitly, 0 or 1; launch 1 first)**: graph replay of the NA video
  decoder on xpu:3 with bounded caches. Captured on the graph chain's chunk 0 (≈ 5–15 s for that decode),
  qualified by byte identity against the uncached eager decode. A mismatch, a refused capture, or a
  decoder difference in the verdict latches the server and writes
  `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/decoder-graph-116-refused.json`; while that file
  exists the launcher refuses `LTX_DECODER_GRAPH=1` (also in `--check-only`). Next step then: an owner
  review of the receipts, archive the latch, relaunch with `LTX_DECODER_GRAPH=0` (5-minute gap, fresh
  health receipt). No automatic fallback.
- **`LTX_BENCODE_OVERLAP`**: not implemented; leave unset (the launcher refuses `1`).
- **Names:** `stream116-…`; the launcher refuses any 116 setup/qualification name or `stream116-` entry under
  `output/`, `output/validation/`, `requests/` (also `--check-only`).
- Same model files and native code as 115 (sampler, decoder source, upsampler, text encoder, `nodes_lt.py`,
  `conditioning_guard.py`, `latent_anchor.py`: byte-for-byte). Same floors (8/8/2/9 GiB before each chunk,
  2 GiB after, 9 GiB xpu:3 before every decode and before each conditioning stage), same latches.

## 1. Fresh admission (immediately before launch)

1. **No other stream server running**, by the controlled single stop of whatever unit is live (an
   application stop, not a host restart), stream client first. Nothing may own port 8188. **Five-minute
   gap** between that stop and this launch. No retry, no restart loop.
2. **`FAULT.json` absent** at the results root, and **`decoder-graph-116-refused.json` absent** for
   `LTX_DECODER_GRAPH=1`.
3. **Health receipt:** four-card postflight probe, same boot, under 6 hours old. Do not poll xpu-smi while
   a server initialises.
4. **Storage** (the launcher repeats it):

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-116-frame-dg1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   At build time (2026-10-08 17:22 UTC): 117,403,774,976 bytes available against 56,908,316,672 required;
   114,182,549,504 would remain after the 3 GiB allowance (49 and 97 admitted). Build admission:
   117,523,959,808 available, 57,076,088,832 required.
5. **Names:** `ls output output/validation requests | grep stream116` must print nothing.
6. **No `__pycache__`** in the packet (0 after the build and after the `--check-only` runs). Use `-B`.
7. **Rehearsal** (passed 2026-10-08 for 49/97 frame dg1, 49/97 frame dg0, 49 mixed dg1, 97 latent dg1,
   49 guide dg1 on two-way20-28, with `postflight-stream115-guide.json`): the launch command with
   `--check-only`, venv Python, soft `NOFILE` 65536 (hard 1048576), not through systemd-run.

## 2. Launch command (frame anchor, decoder graph on)

Recommended order: **97 frames dg1** (the target: ≈1.1 s of work per s of video predicted), then 49 dg1 for
A/B; dg0 only if the decoder graph is refused or for the 116a-alone measurement.

```
systemd-run --user --unit=ltx116-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_ANCHOR=frame LTX_DECODER_GRAPH=1 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 \
  LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 \
  LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=97 LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116 \
  --manifest-sha256 6bced5b4e9ad7b1c69d530c172244f24414fdd4b270d0fa8ba9302d8d047c2db \
  --run-name encoder-server-continuation-stream-116-frame-dg1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
  --health-receipt <fresh four-card health receipt>
```

Run names: `encoder-server-continuation-stream-116-<anchor>-dg<0|1>-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`
matching `LTX_ANCHOR`, `LTX_DECODER_GRAPH`, `LTX_SAMPLER_PLACEMENT`, `LTX_STREAM_FRAMES` (the launcher
refuses any mismatch). The four frame variants on two-way20-28:

| frames | decoder graph | run name |
|---|---|---|
| 97 | 1 | `encoder-server-continuation-stream-116-frame-dg1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97` |
| 49 | 1 | `encoder-server-continuation-stream-116-frame-dg1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49` |
| 97 | 0 | `encoder-server-continuation-stream-116-frame-dg0-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97` |
| 49 | 0 | `encoder-server-continuation-stream-116-frame-dg0-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49` |

## 3. Health and identity after start

`GET /ltx-stream/status`: `phase: "stream_setup"`, `halted: null`, `fault: false`, `packet: 116`,
`anchor: "frame"`, `decoder_graph: 1`, `frames`, `placement: "two-way20-28"`, `text_reuse: 1`,
`features.frame_anchor: true`, `features.video_first_handoff: true`, `features.decoder_graph: true`,
`features.bencode_overlap: false`, `decode_worker.failed: null`, `runtime_manifest_sha256` as above.
After `stream116-prepare`: `stream-decoder-graph-install.json` (dg1) names the pinned decoder source,
the eager na3d file and `na3d_dispatch: comfy_kitchen.backends.eager.na.na3d`; nothing is captured yet.

## 4. Memory (estimates; the floors are the stop rule)

| card | 49, dg1 | 97, dg1 | dg0 | floor |
|---|---|---|---|---|
| xpu:0 / xpu:1 | as 115 / 114 (10.3 / 10.9 GB free at 49; 10.3 / 10.7 at 97) | same | same | 8 GiB |
| xpu:3 | decoder graph pool + static buffers ≈ 1.9 GB held for the server's life (eager decode transient 1.62 GB + context in/out 2 × 103 MB + images/noise 2 × 19 MB): free ≈ 14.0 → ≈ 12.0 GB | ≈ 2.6 GB (2.14 GB + 2 × 206 MB + 2 × 38 MB): free ≈ 15.6 → ≈ 13.0 GB | as 115 (14.0 / 15.6 GB free) | 9 GiB (9.66 GB) before every decode and each conditioning stage |

The graph chain's chunk 0 adds one more transient decode peak for a few seconds (eager reference + capture,
≈ +1.6 / +2.1 GB). Actual pool numbers: `decode-stream116-qgraph-c000000.json` → `decoder`,
`stream-freeze.json` → `decoder_graph.captures[].memory_before/after` (allocated and reserved, xpu:3).
Frame mode runs two 256² VAE encodes per anchored chunk (stages A and B), as 113. Sampler signatures per
route: 4, ceiling 8.

## 5. Qualification (11 requests and one verdict action)

Client (default) or `resolution/components/qualify_client.py --frames 97 --anchor frame --decoder-graph 1
--placement two-way20-28 --text-reuse 1`. Order: window probe, prepare, eager chain (3), graph chain (3),
repeat chain (3, stream form), verdict. Eager and graph chunks wait for their whole decode; the decode
thread is drained before each of them; the repeat chain overlaps.

**Pass looks like** (`stream-qualification-verdict.json`):

- `passed: true`; `exact_replay[k].all_identical` for k = 0, 1, 2 (latents, anchor file, images, waveform).
- `decoder_graph_rows`: modes `eager ×3, graph ×6`; `new_captures` `0,0,0,2,0,0,0,0,0`;
  `reference_equal` `true` on the three graph-chain chunks; `decoder_graph_failures: []`.
  (dg0: all `eager`, no captures, no references.)
- `reference_check`: three rows, every `per_tensor` true; `reference_source.packet` 113 (49) or 114 (97).
  This is the cross-packet proof that 116a and the decoder caches change no byte: the eager chain equals
  the live 113 frame qualification (49) / the 114 frame f97 qualification (97).
- Signatures 1–8 per route (expect 4). Text reuse at chunk 1 of the graph and repeat chains.

Any failure halts streaming; no retry. A decoder failure also writes the latch (§0).

## 6. Streaming and what to watch

Per chunk (receipt): `timing_s.decode_in_chain` (the chain's wait: video decode + anchor hand-off),
`video_decode_in_chain`, `video_done_to_anchor_ready`, `submit_to_anchor_ready`; (decode record):
`timing_s.video_decode`, `audio_decode`, `hash_and_diagnostics`, `capture_and_record`, `decoder.mode`,
`decoder.replays`; (preview record): `record_written → preview_written`. Expected order per chunk N:
video decode N → anchor N → receipt N → chunk N+1 admitted → (beside N+1) audio N, hashes N, record N,
MP4 N.

Predictions (medians of 100 stream chunks; each falsified outside its range):

| launch | period | `decode_in_chain` |
|---|---|---|
| 97 frame dg1 | 4.2–4.7 s | 0.6–0.9 s |
| 49 frame dg1 | 3.2–3.6 s | 0.4–0.6 s |
| 97 frame dg0 (116a alone) | 4.6–5.1 s | 1.15–1.4 s |
| 49 frame dg0 | 3.5–3.9 s | 0.75–0.95 s |

Sharpness (decode records): frames 0–12 at 0.93–1.0 of mid on anchored chunks (as 113).

Stop rules as 115: any eager/replay difference latches; floor refusal, decode/preview failure (including an
audio failure after the hand-off), a decoder-graph refusal or a new decoder signature after the freeze
latch. A GPU fault halts new requests; one controlled stop (`systemctl --user stop
ltx116-stream-server-20261008`, one SIGINT) is the single incident action. No restart loop, no reboot,
no settings change.

## 7. Owner view

Twenty stream chunks of `data/stream/kittens-01.json` (fixed `--base-seed`) at 97 frames: 116 frame dg1
against 115 mixed f97 (when run) with `recovery/20261008-continuation115-stream/owner_seam_view.py`
(`--left`/`--right` run dirs). The owner decides frame (sharp, slower) against mixed (faster, soft first
frames) by looking.
