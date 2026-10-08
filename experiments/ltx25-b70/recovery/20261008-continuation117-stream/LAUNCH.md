# Packet 117 launch procedure (for the coordinator; the authoring agent never launches)

**117 = 116b + four frame-anchor levers, each launch-selectable and exact by construction, plus 121-frame
chunks.** The defaults (`cone`, `1`, `1`) are what the first launch should run, so one qualification
exercises all of them. Every lever is gated twice: in qualification (eager chain with every lever off,
graph chain with the levers on AND their native counterparts on the same inputs, repeat chain with the
levers on in the stream form; every tensor byte-identical across the three) and, for the cone, on every
stream chunk (the full display decode's last frame must equal the cone's anchor). A lever failure latches
the server and writes that lever's latch; the launcher then refuses the lever until an owner archives it.

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-117` |
| Manifest SHA-256 | `5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9` |
| Payload | 118,824,767 bytes (`du -sb`; 116b was 116,685,111) |
| Parent | packet 116b, manifest `06688f41…70442b` (verified at load and at launch, with 116 … 111 behind it) |
| Plan | `8390d15e01a7107948484ea76f90b2661a31a68a42e1b2a72fb803835e55d4c4`; 132 qualification ids (frames/placement/anchor/decoder graph/levers), 264 graph pins per qualification row |
| Build receipt | `data/resume-20261008/continuation117-build.json` |
| Unit | `ltx117-stream-server-20261008` |
| Client | `stream/ltx_continuation_client.py --packet 117 --expect-anchor frame --expect-decoder-graph 1 --expect-anchor-decode cone --expect-bencode-overlap 1 --expect-prep-ahead 1` |

## 0. What is different from 116b, operationally

- **`LTX_ANCHOR_DECODE=full|cone`** (set explicitly; frame anchor only, other anchors `full`). `cone`: the
  decode the chain waits for is the native `VAEDecode` with a cone-restricted stage-5 step
  (`stream_anchor_decode.py`): it issues only the context_proj/qkv/proj/SwiGLU chunk calls and na3d query
  tiles whose frames reach the last pixel frame (34% of the stage-5 na3d tiles at 97 frames, 26% at 121; 30–46%
  of the stage-5 GEMM rows at 97); the full display decode follows on the decode thread once the next
  chunk's sampler A has started (bounded 3 s) and must equal the anchor byte for byte. Mismatch or a failed
  cone → latch `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/anchor-decode-117-refused.json`.
- **`LTX_BENCODE_OVERLAP=0|1`** (set explicitly; frame only, others `0`). `1`: the stage-B anchor encode runs
  on the decode thread when the next chunk's sampler A starts, between xpu:3-only safety snapshots
  (`precompute_guard.Xpu3Snapshot`, 9 GiB before / 2 GiB after on xpu:3, residence of the three xpu:3 roles,
  fault, phase, VAE binding, encoder cache), under an encoder lock that keeps it apart from every
  prompt-thread conditioning call; the stage-B node then runs the native `LTXVImgToVideoInplace` with the
  precomputed encode INSIDE the unchanged four-card conditioning guard (8/8/2/9 GiB before, 2 GiB after).
- **`LTX_PREP_AHEAD=0|1`** (set explicitly; frame only, others `0`). `1`: the stage-A anchor encode runs on
  the decode thread right after the chunk's receipt commits, same guard, consumed the same way.
- **`LTX_STREAM_FRAMES=49|97|121`** (set explicitly). 121 = 5.04 s chunks (120 new frames per anchored
  chunk), 16 latent frames, 256/1024 tokens; audio `[1,8,126,16]`, waveform 240,480 samples, from the
  sealed formulas, checked on the first eager chunk (`stream-geometry-measured.json`).
- **Latches checked by the launcher (also `--check-only`)**: `decoder-graph-116-refused.json` refuses
  `LTX_DECODER_GRAPH=1` (shared with 116/116b), `anchor-decode-117-refused.json` refuses
  `LTX_ANCHOR_DECODE=cone`, `precompute-117-refused.json` refuses `LTX_BENCODE_OVERLAP=1` and
  `LTX_PREP_AHEAD=1`. None exists at the build.
- **Names:** `stream117-…`; the launcher refuses any 117 setup/qualification name or `stream117-` entry under
  `output/`, `output/validation/`, `requests/` (also `--check-only`). The 116b run's `stream116b-` names do not
  collide.
- Same model files and native code as 116b (sampler, decoder source, upsampler, text encoder,
  `nodes_lt.py`, `conditioning_guard.py`, `candidate_safety.py`, `native_bindings.py`, `latent_anchor.py`:
  byte-for-byte). Same floors and latches as 116b, plus the encode guard's xpu:3 floors.

## 1. Fresh admission (immediately before launch)

1. **No other stream server running**, by the controlled single stop of whatever unit is live (an
   application stop, not a host restart), stream client first. Nothing may own port 8188 (the Flash-Next lane
   may be using the cards: wait for its controlled stop, never touch it). **Five-minute gap** between that
   stop and this launch. No retry, no restart loop.
2. **`FAULT.json` absent** at the results root; the three latch files above absent for the levers you set.
3. **Health receipt:** four-card postflight probe, same boot, under 6 hours old. Do not poll xpu-smi while a
   server initialises.
4. **Storage** (the launcher repeats it):

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-117/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-117-frame-dg1-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   At build time: 111,150,616,576 bytes available against 57,076,088,832 required for the build (50 GiB reserve + 3 GiB run + 160 MiB build); 110,982,844,416 remained after the build allowance.
5. **Names:** `ls output output/validation requests | grep stream117` must print nothing.
6. **No `__pycache__`** in the packet (0 after the build and after the `--check-only` runs). Use `-B`.
7. **Rehearsal:** the launch command with `--check-only`, venv Python, soft `NOFILE` >= 65536 (hard 1048576), not
   through systemd-run. **Not yet passed:** at the build (2026-10-08 ~21:30 UTC) all seven variants passed the
   environment/lever/latch rules, the run-name and run-dir checks, the full packet verification, the naming
   preflight, the dependency activation and the runtime verification, then refused at `verify_model_receipt`
   because `FAULT.json` exists (four-card device fault at 21:11 UTC during the Flash-Next calibrate-load; owner
   reboot decision). Rerun the rehearsal after the fault is cleared and with a fresh health receipt (a reboot
   changes the boot id; `postflight-stream116b.json` will not admit).

## 2. Launch command (recommended first launch: 97 frames, frame anchor, every lever on)

```
systemd-run --user --unit=ltx117-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_ANCHOR=frame LTX_DECODER_GRAPH=1 LTX_ANCHOR_DECODE=cone LTX_BENCODE_OVERLAP=1 \
  LTX_PREP_AHEAD=1 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 \
  LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 \
  LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=97 LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-117/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-117 \
  --manifest-sha256 5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9 \
  --run-name encoder-server-continuation-stream-117-frame-dg1-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
  --health-receipt <fresh four-card health receipt>
```

Run names: `encoder-server-continuation-stream-117-<anchor>-dg<0|1>-ad<full|cone>-bo<0|1>-pa<0|1>-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`,
matching `LTX_ANCHOR`, `LTX_DECODER_GRAPH`, `LTX_ANCHOR_DECODE`, `LTX_BENCODE_OVERLAP`, `LTX_PREP_AHEAD`,
`LTX_SAMPLER_PLACEMENT`, `LTX_STREAM_FRAMES` (the launcher refuses any mismatch; 132 names exist, the
levers vary only with the frame anchor). The launches that matter, on two-way20-28:

| order | frames | dg | levers | run name | why |
|---|---|---|---|---|---|
| 1 | 97 | 1 | cone/1/1 | `…-117-frame-dg1-adcone-bo1-pa1-two-way20-28-…-f97` | target: every lever at once |
| 2 | 121 | 1 | cone/1/1 | `…-117-frame-dg1-adcone-bo1-pa1-two-way20-28-…-f121` | ≈1.0–1.1 s of work per s of video |
| 3 | 97 | 1 | full/0/0 | `…-117-frame-dg1-adfull-bo0-pa0-two-way20-28-…-f97` | 116b-equivalent control on 117 code (same bytes, A/B speed) |
| (if needed) | 121 | 0 | cone/1/1 | `…-117-frame-dg0-adcone-bo1-pa1-two-way20-28-…-f121` | if xpu:3 runs short at 121 with the decoder-graph pool |

Per-lever attribution does not need a launch per lever: the receipts split every lever's time (§6). Launch
single-lever variants only if a lever latches or the split is ambiguous.

## 3. Health and identity after start

`GET /ltx-stream/status`: `phase: "stream_setup"`, `halted: null`, `fault: false`, `packet: 117`,
`anchor: "frame"`, `decoder_graph: 1`, `anchor_decode: "cone"`, `bencode_overlap: 1`, `prep_ahead: 1`,
`frames`, `placement: "two-way20-28"`, `text_reuse: 1`, `features.cone_anchor_decode: true`,
`features.bencode_overlap: true`, `features.prep_ahead: true`, `features.chunk_121: true`,
`decode_worker.failed: null`, `runtime_manifest_sha256` as above. After `stream117-prepare`:
`stream-decoder-graph-install.json` (dg1, `na3d_route`, `outer` added after the cone install) and
`stream-anchor-decode-install.json` (`over: "decoder-graph shadow"` with dg1, `"sealed method"` with dg0, the
pinned decoder and na3d hashes); nothing captured yet.

## 4. Memory (estimates from the 113–116b receipts; the floors are the stop rule)

| card | 97, dg1, levers on | 121, dg1, levers on | 121, dg0 | floor |
|---|---|---|---|---|
| xpu:0 | min free at the stage-B snapshot 10.10 GB on 116b (1.51 GB = 1.41 GiB above 8 GiB); the levers add nothing on xpu:0 | ≈ 9.95–10.0 GB at stage B (the upsampler transient grew 0.28 GB from 49 to 97; ≈ +0.1 GB more at 121): ≈ 1.3 GiB margin | same | 8 GiB |
| xpu:1 | 10.72 GB (2.1 GB margin) | ≈ 10.7 GB | same | 8 GiB |
| xpu:2 | 12.57 GB | ≈ 12.5 GB | same | 2 GiB |
| xpu:3 | 12.09–12.15 GB before every decode on 116b (graph pool + statics ≈ 3.5 GB); the cone's eager stage-5 transient (≈ 1.2 GB at 97) fits in blocks the qualification's eager decodes already reserved; the two encodes need ≈ 75 MB | pool ≈ 4.4 GB (×1.25) → ≈ 11.3 GB before a decode (≈ 1.6 GB above 9.66 GB); the cone transient ≈ 1.8 GB: **if the allocator keeps it reserved on top, the next decode's 9 GiB floor refuses (latch, no damage)** | ≈ 15.6 GB (no pool) | 9 GiB (9.66 GB) before every decode, every conditioning stage and every precomputed encode; 2 GiB after |

Actual numbers: receipts `memory.before/after/conditioning`, decode records `xpu3_free_before_decode`,
`precompute.{A,B}.record.before/after.physical_free_bytes`, `stream-freeze.json` → `decoder_graph.captures`.
Storage: 9 captures of 78 MB (97) / 97.6 MB (121) inside the 3 GiB run allowance.

## 5. Qualification (11 requests and one verdict action)

Client (default) or `resolution/components/qualify_client.py --frames 97 --anchor frame --decoder-graph 1
--anchor-decode cone --bencode-overlap 1 --prep-ahead 1 --placement two-way20-28 --text-reuse 1`. Order:
window probe, prepare, eager chain (3), graph chain (3), repeat chain (3, stream form), verdict.

**Pass looks like** (`stream-qualification-verdict.json`):

- `passed: true`; `exact_replay[k].all_identical` for k = 0, 1, 2 (latents, anchor file, images, waveform).
- `lever_rows`: `anchor_decode` `full ×3, cone ×6`, `cone_equal` true on the six cone chunks; `sources`
  `{A: native, B: native}` on eager chunks 1–2, `{A: precomputed, B: precomputed}` on graph and repeat
  chunks 1–2, `dual_equal` `{A: true, B: true}` on graph chunks 1–2; `anchor_decode_failures: []`,
  `precompute_failures: []`.
- `decoder_graph_rows` as 116b: modes `eager ×3, graph ×6`; `new_captures` `0,0,0,2,0,0,0,0,0`;
  `reference_equal` true on the graph chain; `decoder_graph_failures: []`.
- `reference_check` (49 and 97 frames, two-way20-28, frame): three rows, every `per_tensor` true — the eager
  chain (levers off) equals the packet-113 / packet-114 frame qualification byte for byte. At 121 frames
  there is no earlier reference (`reference_check: null`); the three-chain identity is the gate.
- `stream-geometry-measured.json` `matches: true` (at 121: `waveform [1,2,240480]`, audio `[1,8,126,16]`).

Any failure halts streaming; no retry. A lever failure also writes its latch (§0).

## 6. Streaming: what to watch and the predictions

Per chunk (receipt): `timing_s.anchor_decode_in_chain` (= `video_decode_in_chain`: the cone decode),
`submit_to_sampler_start` (prep-ahead), `sampler_a_split.condition_b_to_concat` (overlap),
`conditioning_sources.{A,B}.waited_s` (how long a stage waited for its precomputed encode; ≈ 0 expected),
`submit_to_anchor_ready`. Decode record: `anchor_decode.{seconds, display_seconds, equal}`,
`timing_s.{precompute_a, anchor_ready_to_go, precompute_b, display_decode, audio_decode}`,
`schedule.{commit, go}` (`go: "sampler-a-start"` expected on every chunk but the last).

Predictions (medians of 100 stream chunks after the first 10, frame anchor, dg1, text reuse; 116b measured
5.54 s at 97: submit→sampler A 0.435, sampler A 1.624, stage-B conditioning 0.265, sampler B 1.195,
chain decode 1.572 + 0.030 hand-off, receipt 0.115, client turnaround 0.156):

| item | 97 frames | 121 frames |
|---|---|---|
| chain decode (`anchor_decode_in_chain`) | 0.65–0.95 s (cone; 1.57 full) | 0.70–1.00 s |
| `submit_to_sampler_start` | 0.33–0.40 s | 0.33–0.40 s |
| stage-B conditioning (`condition_b_to_concat`) | 0.14–0.20 s | 0.14–0.20 s |
| display decode off the chain (`display_decode`) | 1.5–1.7 s | 1.9–2.2 s |
| period (submit to submit) | **4.35–4.9 s (central 4.6; target ≤ 4.4)** | **5.2–5.8 s (central 5.35)** |
| work per second of video | 1.08–1.21 s/s | 1.03–1.15 s/s |

Seams as 113–116b (frame anchor): frames 0–12 at 0.93–1.0 of mid-chunk sharpness, same bytes as 116b.

Stop rules as 116b plus: a cone mismatch or a precompute guard refusal latches. A GPU fault halts new
requests; one controlled stop (`systemctl --user stop ltx117-stream-server-20261008`, one SIGINT) is the
single incident action. No restart loop, no reboot, no settings change.

## 7. Owner view

As 116b: twenty stream chunks of `data/stream/kittens-01.json` (fixed `--base-seed`) at 97 and at 121
frames with `recovery/20261008-continuation115-stream/owner_seam_view.py`. The bytes at 97 are 116b's by
the gate, so only the 121-frame seams are new to look at.
