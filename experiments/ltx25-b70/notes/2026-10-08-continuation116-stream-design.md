# Continuation 116: frame anchor by default, 116a scheduling, decoder graph experiment (built, not launched)

*2026-10-08. CPU only: no GPU, no server, nothing launched. Sources and tests:
`recovery/20261008-continuation116-stream/`. Build receipt: `data/resume-20261008/continuation116-build.json`.
Packet: `prepared-continuation-stream-116` (manifest in the receipt). Specification:
`notes/2026-10-08-continuation-tail-decode-design.md` (option 116a, the gate, the decode-path breakdown, why a
tail decode is not exact) and the owner authorization of 2026-10-08 for bounded decoder caches as gated
experiments.*

## Why

Measurements on the 113-115 servers: latent, mixed and guide anchors soften the first ~12 frames of every
chunk (0.55-0.85 of mid-chunk sharpness); only the decoded-frame anchor at both stages (113, `frame`) is
sharp (0.93-1.00). The frame anchor costs time because the chain must wait for the decode: with text
reuse, ≈4.1 s per 2.04 s chunk at 49 frames and ≈5.4 s per 4.04 s chunk at 97 (114 frame f97 measured
`decode_in_chain` 2.0 s and `submit_to_anchor_ready` 5.65 s). A tail decode cannot produce the anchor
exactly (the NA decoder's last frame depends on every latent frame; tail-decode note §1), so 116 keeps the
whole decode and removes everything else from the chain, and tries to make the decode itself cheaper
without changing a byte.

## What 116 is

Packet 115 (all four anchor modes, sharpness profile, 49/97 frames, text reuse, naming rule, coredump
fix) plus:

1. **Default anchor `frame`** (113 semantics at both stages). `mixed`, `latent`, `guide` stay for A/B.
2. **116a scheduling** (frame mode). The output node hands the decode to the decode thread and waits for
   the job stage `anchor` only (`stream_decode.OrderedWorker.publish / wait_stage`, bounded 300 s). The
   decode thread runs, in this order:
   1. video decode (`nodes.VAEDecode`, unchanged; its F32 cast and clamp are the native ones) → `video_done`;
   2. shape check, last frame → anchor file (exclusive, finiteness check, fsync, ≈24 ms) → `anchor_ready`
      → **hand-off**; the chain commits the receipt and the client submits chunk N+1;
   3. audio decode → `audio_done` (= `decode_done`);
   4. SHA-256 and finiteness of images and waveform, border and sharpness diagnostics → `hashed`;
   5. qualification capture (qualification chunks only);
   6. decode record (validated, exclusive, fsynced; `record_staged` inside it, `record_written` after);
   7. preview copies and the MP4 hand-off → preview record (`record_written`, `preview_written`).
   Gated qualification chunks (eager and graph chains) wait for the whole decode in every anchor mode, so
   nothing is decoded, captured or replayed beside them; the repeat chain and the stream overlap.
3. **Decoder graph** (`LTX_DECODER_GRAPH=0|1`, default 1; `stream_decoder_graph.py`). Graph replay of
   `NADiffusionDecoder.forward_pre_diffusion` and `forward_diff_step` with bounded, device-resident caches,
   keyed by shape and device, filled only outside capture:
   - RoPE inverse frequencies: the original `rope_inv_freqs` (fp64 on the CPU, as the B70 has no fp64) is
     called once per (dim, base, device) and its device tensor kept (2 entries);
   - NA window masks: the per-axis boolean matrix of `_group_mask` per (starts, ends, device), built with the
     original expressions (`torch.tensor`, `int(en.max())`); the rest of `_group_mask` runs as written
     (19 entries at 49 frames, 21 at 97, ≤ 416 elements each; bounds 64 / 4096);
   - decoder noise: drawn once per (shape, dtype, device) with the generator `CausalDiffusionVAE.decode`
     creates, after checking it is in the fresh seed-0 state (bound 1: one stream geometry per server).
   Capture follows packet 22/26 (`ltx_graph_vae.py`): static mirrors, eager reference, warm-up on a side
   stream, capture into one shared pool on xpu:3 under the sampler's exclusive `CAPTURE_LOCK`, output
   copied to a buffer allocated outside the capture, then three proofs (input sensitivity, replay
   reproducibility, replay == eager reference bit for bit). A cache miss during capture raises before a
   host copy can be recorded. One signature per method (bound 2); `freeze()` after the verdict.
   Outside `graph_decode()` every shadow calls the original function or method: the uncached eager decode
   is packet 115's code path.
4. **LTX_BENCODE_OVERLAP not implemented** (the launcher refuses `1`). The stage-B anchor encode can only
   overlap stage A if it runs on another thread with a guard snapshot that synchronises xpu:3 alone. The
   guard's `_snapshot` is the sealed `NativeReferenceSafety._snapshot` (`for card in CARDS:
   self.synchronize(card)`, pinned by `CONTROLLER_SHA256`), and the guard is bound to the prompt thread and
   the controller's active request (`_identity`: `threading.get_ident() == self.thread_ident`). Snapshotting
   xpu:3 alone means dropping the xpu:0/1/2 floor checks at that point or editing the pinned controller;
   either weakens the checks. Left out, with the reason recorded here and in the plan.

## Exactness

- **116a** changes no arithmetic: the same native calls on the same inputs, in a different order on one
  thread. The video and audio decoders are independent (no shared RNG: the video RNG is call-local, the
  audio decoder has none).
- **Decoder graph**, by construction: each cache stores what the original code computes from the same
  inputs (CPU-tested: every mask group of the real 49/97 geometry byte-identical to the original
  `_group_mask`, bf16; whole decodes of the sealed decoder at small widths, real kernels/upsamples/pads,
  fp32 and bf16, many mask tiles: uncached == capture == replay == replay with new latents, byte for byte).
  On XPU only the live gate can show it.
- **The gate** (qualification_gate.decide): 115's eager/graph/repeat comparison of every tensor, plus
  - decoder graph on: eager chain decoded uncached; each graph-chain chunk decoded twice on the same
    latents (uncached first) with byte-identical images; graph chain chunk 0 captures exactly the two
    graphs, nothing later captures; one signature per method; identical latents with different decoded
    tensors across chains is flagged as a decoder failure. Any of these latches and writes
    `decoder-graph-116-refused.json` in the results root; the launcher then refuses `LTX_DECODER_GRAPH=1`
    (no automatic fallback: relaunch with 0 after review);
  - cross-packet reference (`resolution/reference-frame-hashes.json`, re-read from each source verdict's own
    run directory): for `49/two-way20-28/frame` (packet 113) and `97/two-way20-28/frame` (packet 114's frame
    run) the eager chain's video, audio and stage-A latents (97), images, waveform, last frame and anchor
    file must equal the reference byte for byte. This proves 116a and the decoder caches change no output.

## Predictions (medians of 100 stream chunks, frame anchor, two-way20-28, text reuse 1; falsified outside)

| launch | period (start to start) | chain decode (`decode_in_chain`) | other |
|---|---|---|---|
| 49, LTX_DECODER_GRAPH=0 (116a alone) | 3.5–3.9 s (design ≈3.7) | 0.75–0.95 s | receipt before `audio_done` on every stream chunk |
| 97, LTX_DECODER_GRAPH=0 | 4.6–5.1 s (design ≈4.9) | 1.15–1.4 s | |
| 49, LTX_DECODER_GRAPH=1 | 3.2–3.6 s | 0.4–0.6 s (video replay 0.35–0.5 s) | qgraph c0 decode ≤ 15 s (capture + proofs) |
| 97, LTX_DECODER_GRAPH=1 | 4.2–4.7 s (≈1.05–1.15 s of work per s of video) | 0.6–0.9 s | |

Decoder estimate: per decode at 49 frames the eager na3d builds 246 mask groups, each with three host
reads (`int(en.max())`, a device sync) and six host-to-device copies (738 syncs, 1,476 copies), and issues
1,054 SDPA calls (2,098 at 97); the decode runs at 0.97–1.33 CPU core-s per wall s (sync- and dispatch-
bound). Replay removes the syncs, the copies and the Python dispatch; the GPU kernel time is not measured
for this decoder. Assumed 45–60% of the video decode is dispatch/sync, i.e. 0.75 → 0.35–0.5 s at 49 and
1.2 → 0.55–0.8 s at 97 (the sampler's graph capture cut 1.86×).

Sharpness: frame-anchored chunks at 0.93–1.0 of mid over frames 0–12, as 113 (same bytes).

## Memory (xpu:3)

The decoder graph keeps one shared pool plus static buffers on xpu:3: ≈ the eager decode's transient peak
(peak − allocated on the live receipts: 1.62 GB at 49, 2.14 GB at 97) plus static inputs/outputs (context
2 × 103 MB at 49 / 2 × 206 MB at 97, images and noise 2 × 19 / 2 × 38 MB): **≈1.9 GB at 49, ≈2.6 GB at
97**, held for the server's life. Free before a decode was 14.0 GB (49) / 15.6 GB (97) on the live
receipts, so ≈12 / ≈13 GB remain against the unchanged 9 GiB (9.66 GB) pre-decode and pre-encode floors.
During the graph chain's chunk 0 the eager reference and the capture add one more transient peak (≈1.6 /
2.1 GB) for a few seconds. The capture records `memory_allocated/reserved` of xpu:3 before and after each
method (`stream-decoder-graph-install.json`, `decode-*.json` `decoder`, `stream-freeze.json`).

## What could not be checked on CPU

Everything on XPU: whether `torch.xpu.graph` captures this decoder at all (SDPA with additive masks in
bf16, the triton `rms_rope_` kernel, the einops views, the comfy_kitchen custom-op dispatch) and replays
it bit-identically; the pool size; capture time; the speed of 116a and of the replay; the contention of the
moved audio decode and hashing (CPU and GIL) with the next chunk's text and stage A; whether the stage-A
VAE encode on the prompt thread beside the audio decode on the decode thread (both xpu:3, different
models, registry-locked loads) changes any timing materially. The CPU suites exercise the real runtime
through setup, qualification, the verdict and streaming with a fake decoder graph (and the real controller
on the sealed decoder with a fake graph API).

## Open questions

1. If the live gate refuses the decoder graph, which proof failed (the receipts name it): a refusal before
   any wrong pixel is a schedule cost, not a quality risk. 116b (cone-restricted anchor decode) is the
   remaining exact decode lever at 97 frames.
2. Audio is still unconditioned per chunk and 0.03 s shorter than the video (as 113-115).
3. The owner A/B at 97 frames: 116 frame (sharp, ≈1.1 s/s predicted with the decoder graph) against 115
   mixed (soft first frames, ≈1.0 s/s).
