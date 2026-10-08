# Packet 115 launch procedure (for the coordinator; the authoring agent never launches)

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115` |
| Manifest SHA-256 | `a934bac2ba8f9673f98f7b1186919d341c74b10e54f308979ca9cff5ef4c7137` |
| Payload | 114,467,679 bytes (`du -sb`; 114 was 113,443,722) |
| Parent | packet 114, manifest `3e8b7abe…c97f3` (verified at load and at launch, with 113, 112 and 111 behind it) |
| Plan | `c5b94b1e…c2c689`; 16 qualification ids (frames/placement/anchor), 32 graph pins per qualification row |
| Build receipt | `data/resume-20261008/continuation115-build.json` |
| Unit | `ltx115-stream-server-20261008` |
| Client | `stream/ltx_continuation_client.py --packet 115` |

## 0. What is different from 114, operationally

- **Anchor mode `mixed` is the default** (`LTX_ANCHOR=mixed`): stage A on the latent anchor (as 114),
  stage B on the predecessor's decoded last frame through the native image conditioning with its VAE
  encode (as 113). Chunk N+1's text encode and stage A run while chunk N decodes; chunk N+1's stage B
  waits for chunk N's decode record (bounded 300 s). Motivation: the live 114 latent anchor left frames
  0-5 of every chunk at 0.60-0.83 of mid-chunk sharpness (owner rule: never sacrifice quality).
- **`LTX_ANCHOR=guide`**: the native latent guide (last two latents of chunk N, latent index -2) for both
  stages; anchored chunks deliver all 49/97 frames. `latent` (114) and `frame` (113) stay for A/B.
- **Sharpness profile** in every decode record (frames 0, 1, 2, 5, 10, 24, mid, last; relative to mid).
- **Launcher fault pattern (live 114 finding, 2026-10-08 15:06:16 UTC).** The 114 f97 server latched
  FAULT on `xe 0000:43:00.0: [drm] Xe device coredump has been deleted.` — the driver clearing the
  devcoredump of the 14:04 incident; the bare `coredump` term in `GPU_FAULT` matched it, and no new
  fault happened. 115's `serve-encoder.py` (builder transform `launcher_source`) adds
  `COREDUMP_DELETED = re.compile(r'coredump has been deleted', re.I)` and excludes such lines in
  `classify_journal` (the in-run watcher, the preflight and the same-boot admission) and in
  `fault_lines`. Creation lines (`Xe device coredump has been created`, `Check your
  /sys/class/drm/card0/device/devcoredump/data`) and the `xe_devcoredump` / `devcoredump_snapshot`
  trace still latch; `HOST_STALL` is unchanged. CPU test `test_runtime_packet.CoredumpPattern` runs the
  old and new launcher on the real journal lines. Note: the health probe
  (`scripts/check-four-card-health.py`) has its own fault list and is not changed by 115; if a deletion
  line falls inside a probe window the probe will still refuse.
- **Names:** `stream115-…`; the launcher refuses any 115 setup/qualification name or any `stream115-`
  entry under `output/`, `output/validation/` or `requests/` (also in `--check-only`). `stream114-`
  entries do not collide.
- Same model files as 114 (sampler, decoder, upsampler, text encoder, `nodes_lt.py` with the native
  conditioning and guide nodes: byte-for-byte). `conditioning_guard.py` changes only its stage-order
  bookkeeping (`first_stage='B'`, derived from sealed 111 by `derive_from_111.guard115`). Same floors
  (8/8/2/9 GiB before each chunk, 2 GiB after, 9 GiB xpu:3 before every decode), same latches.

## 1. Fresh admission (immediately before launch)

1. **No 114 server running**, by the controlled single stop of whatever unit is live (an application
   stop, not a host restart), stream client first. Nothing may own port 8188. **Five-minute gap** between
   that stop and this launch. No retry, no restart loop.
2. **`FAULT.json` absent** at the results root (the launcher refuses otherwise). The 15:06 false latch was
   archived to `fault-archive/` by the coordinator.
3. **Health receipt:** four-card postflight probe, same boot, under 6 hours old. Do not poll xpu-smi while
   a server initialises.
4. **Storage** (the launcher repeats it):

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-115-mixed-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   At build time (2026-10-08 ~15:25 UTC): 119,590,686,720 bytes available against 56,908,316,672
   required; 116,369,461,248 would remain after the 3 GiB allowance (49/97 × mixed/guide all admitted).
5. **Names:** `ls output output/validation requests | grep stream115` must print nothing.
6. **No `__pycache__`** in the packet (0 after the build and after the `--check-only` runs). Use `-B`.
7. **Rehearsal** (passed 2026-10-08 for 49/mixed, 97/mixed, 49/guide, 97/guide, 49/latent, 49/frame on
   two-way20-28 with `postflight-stream114-f97.json`): the launch command with `--check-only`, venv Python,
   not through systemd-run. No device, lock or port work.

## 2. Launch command (49 frames, mixed anchor) — launch 49 first

Run name `encoder-server-continuation-stream-115-mixed-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49`.

```
systemd-run --user --unit=ltx115-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_ANCHOR=mixed LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 \
  LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 \
  LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=49 LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115 \
  --manifest-sha256 a934bac2ba8f9673f98f7b1186919d341c74b10e54f308979ca9cff5ef4c7137 \
  --run-name encoder-server-continuation-stream-115-mixed-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49 \
  --health-receipt <fresh four-card health receipt>
```

Run names per variant: `encoder-server-continuation-stream-115-<anchor>-two-way20-28-w1-b1-p1-dxpu2-s256x256-f<frames>`
with `<anchor>` ∈ {mixed, guide, latent, frame} and `<frames>` ∈ {49, 97}, matching `LTX_ANCHOR` and
`LTX_STREAM_FRAMES` (the launcher refuses any mismatch).

## 3. Health and identity after start

`GET /ltx-stream/status`: `phase: "stream_setup"`, `halted: null`, `fault: false`, `packet: 115`,
`anchor: "mixed"`, `frames: 49`, `placement: "two-way20-28"`, `text_reuse: 1`, `features.mixed_anchor: true`
(`guide_anchor` / `latent_anchor` true on those launches), `features.sharpness_diagnostic: true`,
`decode_worker.failed: null`, `runtime_manifest_sha256` as above. After `stream115-prepare`,
`stream-native-binding.json` names the pinned `nodes_lt.py` guide nodes.

## 4. Memory (estimates; the floors are the stop rule)

| card | mixed 49 | mixed 97 | guide 49 | guide 97 | floor |
|---|---|---|---|---|---|
| xpu:0 / xpu:1 | as 114 latent (10.27 / 10.86 GB free measured at 49; 10.33 / 10.72 at 97) | as 114 at 97 | anchored signatures at 144 / 576 tokens instead of 112 / 448: pool +≈0.1 GiB | 240 / 960 instead of 208 / 832: +≈0.1 GiB | 8 GiB |
| xpu:3 | + one 256² VAE encode per chunk after the decode finished (113 ran two); the encode never overlaps the decode (stage B waits) | same | no encode | no encode | 9 GiB, also before every decode |

Signatures per route: 4 in every mode (unanchored A/B + anchored A/B); guide replaces the anchored pair with
the guided shapes. Ceiling 8, unchanged. Storage per chunk adds, for mixed, the 786,432-byte frame anchor
(the two newest stream frame files are kept); guide anchors are 81,920 bytes.

## 5. Qualification (11 requests and one verdict action)

Client (default) or `resolution/components/qualify_client.py --frames 49 --anchor mixed --placement
two-way20-28 --text-reuse 1`. Order and chains as 114 (`stream115-…`). Decode drained before every eager
and graph request; the repeat chain overlaps.

**Pass looks like:** verdict `passed: true`; `exact_replay[k].all_identical` for k = 0, 1, 2 (latents,
anchor file, decode images and waveform; mixed adds `frame_anchor_in` for k = 1, 2). For mixed, every
anchored chunk's `anchor_in.frame.sha256` equals its predecessor's decode-record last frame and capture
last frame. `mixed_frame_wait_s` and `sharpness_relative_by_chunk` are reported, not gated. Signatures
1-8 per route (expect 4). `slot0_pin` (mixed: A) and `guide_pin` (guide: A, B): expect `bytes_equal`
or signed-zero only.

**Cross-checks (CPU predictions, reference `reference-114-qualification-hashes.json`, from the live 114 f49
run, two-way20-28, text reuse 1):**

- Every 115 mode at 49 frames: `stream115-qeager-c000000` images / video / audio / stage A / waveform
  byte-identical to `stream114-qeager-c000000` (chunk 0 is unanchored; also equal to 113's
  `206e1860…` images).
- **Mixed: `stage_a_latent` of `qeager-c000001` and `-c000002` byte-identical to 114's** (the stage-A
  chain depends only on stage-A anchors, the text and the seed, which mixed and latent share). Video
  latents, images and waveform differ from 114 (stage B differs).
- Latent: all three chunks identical to 114's. Frame: all three identical to 113's
  (`recovery/20261008-continuation114-stream/reference-113-qualification-hashes.json`).

A mismatch is a finding to report even if the 115 verdict passed. Any failure latches; no retry.

## 6. Streaming and what to watch

Per chunk: `timing_s.submit_to_anchor_ready`, `timing_s.frame_wait` (mixed), the decode record's
`timing_s.anchor_ready_to_decode_done` and `sharpness`. Expected wait points (mixed):

1. N's output node: latents hashed, latent file fsynced → `anchor_ready` → receipt committed → decode N queued.
2. N+1 admitted (client turnaround ≈ 0.2 s): text (reuse ≈ 0.1 s, fresh ≈ 0.5 s) + stage A (1.35 s at 49,
   1.64 s at 97) + upsampler, **while decode N runs** (1.52 s at 49, 2.45 s at 97, measured on 114).
3. N+1's `stream_condition_b` starts → **waits for decode record N** (`frame_wait`) → reads frame N →
   native VAE encode on the prompt thread (decode thread idle) → stage B → output.

Predictions (medians of 100 stream chunks; each falsified outside its range):

| launch | start-to-start period | other |
|---|---|---|
| 49 mixed | 2.7–3.1 s (≈ text + A + B + encode) | `frame_wait` median ≤ 0.05 s; sharpness frames 0-5 ≥ 0.9 of mid (median over anchored chunks) |
| 97 mixed | 3.6–4.3 s (≤ 1.08 s of work per s of video) | `frame_wait` median 0.2–0.7 s (decode 2.45 s > text + A ≈ 2.0 s) |
| 49 guide | 2.7–3.0 s | sampler A/B buckets +5–15% vs 114 latent; sharpness frames 0-5 ≥ 0.9 of mid |
| 49 latent (A/B) | 2.5–2.8 s | reproduces the 114 dip (frames 0-5 at 0.6-0.85) |

Stop rules as 114: any eager/replay difference latches; floor refusal, decode/preview failure, a stage-B
wait past 300 s, or a frame anchor whose bytes differ from its decode record latch. A GPU fault halts new
requests; one controlled stop (`systemctl --user stop ltx115-stream-server-20261008`, one SIGINT) is the
single incident action. No restart loop, no reboot, no settings change.

## 7. Owner view: sharpness and seams

Same ten kitten prompts and seeds per run (`data/stream/kittens-01.json`, `--base-seed` fixed), twenty
stream chunks each: 115 mixed f49 (default), 115 guide f49, and the 114 latent f49 run01 already on disk
(`…-114-latent-…-f49.run01-20261008T1434Z`). Each 115 run is its own launch, five-minute gap, fresh health
receipt; archive `output/stream115-*` and `output/validation/stream115-*` between launches.

```
/home/steve/.venvs/ltx25-baseline/bin/python -B /home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream/owner_seam_view.py \
  --left  <114 latent f49 run01 dir> --right <115 mixed f49 run dir> \
  --out   /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/owner-view-115-mixed-vs-114-latent-f49 --seams 19
```

Writes the seam clips and side-by-side stream as 114, plus `sharpness.json`, `sharpness.txt` (printed:
median relative sharpness per frame over anchored chunks, left vs right) and `sharpness-profile.svg`.
115 runs use the decode record's F32 profile; 113/114 runs are measured from the MP4s (labelled
`source: mp4`; compare shapes, not absolute values, across sources). Repeat with `--right <115 guide f49>`.
The owner decides mixed vs guide (vs 114 latent) by looking.
