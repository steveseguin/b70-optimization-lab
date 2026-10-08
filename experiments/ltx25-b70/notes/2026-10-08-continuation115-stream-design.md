# Continuation 115: mixed anchor (default) and latent-guide anchor (built, not launched)

*2026-10-08. CPU only: no GPU, no server, nothing launched. Sources and tests:
`recovery/20261008-continuation115-stream/`. Build receipt: `data/resume-20261008/continuation115-build.json`.
Packet: `prepared-continuation-stream-115`, manifest `a934bac2…4c7137`.*

## Why

The live 114 server (49 frames, latent anchor, 14:45 UTC) passed its exactness gate and reached the anchor
in about 2.3 s with the decode off the chain (period 2.63 s median over 105 chunks). But the per-frame
sharpness (Laplacian variance over 20 chunks) put the first six frames of every chunk at 0.60–0.83 of
mid-chunk (frame 9 at 0.82); the 113 frame anchor showed no dip (1.0–1.15). The latent-anchor design note
predicted the risk: slot 0 is a single-frame slot (causal VAE), and a slot-6 latent covering eight moving
frames is outside what the model was trained on. The owner's rule is never sacrifice quality, so the latent
anchor cannot be the default.

## What 115 is

Packet 114 plus two launch-selectable anchor modes (four in all), a sharpness profile, and one launcher fix.

1. **`LTX_ANCHOR=mixed` (default).** Stage A anchors on chunk N's stage-A output latent (slot T-1, as 114).
   Stage B anchors on chunk N's **decoded last frame** through the native `LTXVImgToVideoInplace` with its
   VAE encode (as 113), re-pinned after the upsampler. Only the stage-A side is out of distribution, and the
   stage-B sampler (sigma 0.85 start, 448 tokens at 256²) is what the viewer sees; the hypothesis is that
   the dip comes from the stage-B slot-6 pin, because stage B fixes fine detail. *Unverified until the
   owner view.*
   - **Scheduling.** The output node of chunk N writes the 40,960-byte latent file, stamps `anchor_ready`,
     commits the receipt and queues the decode (as 114). The decode thread decodes N, writes N's last frame
     as an exclusive, fsynced 786,432-byte frame file, then commits N's decode record (which names it).
     Chunk N+1 is admitted on N's receipt; its text encode and stage A need only N's latent file. Its
     stage-B node (`LTXStreamFrameConditionB115`) consumes the upsampler output, so it starts after stage A;
     it then waits — outside the authority lock, bounded 300 s — for N's decode record
     (`OrderedWorker.wait_for`), re-reads and hashes the record and the frame file, and runs the native
     encode through the stage guard as a stage-B-only request (`conditioning_guard`, `first_stage='B'`).
   - **Wait points**: (a) N+1 waits for N's receipt (client); (b) N+1's stage B waits for N's decode record;
     nothing else. The VAE encode (prompt thread) and the VAE decode (decode thread) never run at the same
     time: N+1's encode starts after N's decode, and N+1's decode is not queued before N+1's output node.
     The CPU harness counts it: `encode_during_decode == 0` in every mixed run.
   - **Cadence**: ≈ text + A + max(0, decode − (turnaround + text + A)) + B-encode + B. Measured on 114:
     at 49 frames decode 1.52 s vs turnaround + text + stage A ≈ 1.8 s, so the wait is ≈ 0 and the period
     ≈ 2.63 + 0.24 (stage-B encode plus its two guard snapshots; the 113 − 114 sampler-A bucket difference)
     ≈ 2.85–2.95 s. At 97 frames decode 2.45 s vs ≈ 2.0 s, so ≈ 0.45 s of wait: ≈ 3.9 s per 96 new frames.
2. **`LTX_ANCHOR=guide`.** The native `LTXVAddLatentGuide` (`nodes_lt.py:525-646`) with the last two latents
   of chunk N (A: node 367 slots T-2..T-1, B: node 369) at latent index −2 for both stages, strength 1.0;
   `LTXVCropGuides` after each sampler, before the upsampler and before the output node. Both are called
   through `GuideGuard` (order guide A, crop A, guide B, crop B; identity, shapes, mask, keyframe count).
   - **Tokens** (checked on CPU by running the sealed native nodes, `test_guide_anchor.py`): +32 stage-A and
     +128 stage-B video tokens: 112→144 and 448→576 at 49 frames, 208→240 and 832→960 at 97. Keyframe
     positions are pixel frames −16..−8 and −8..0 (`causal_fix` off), the guide mask is 0, and at strength
     1.0 with no pixel mask the model builds no `GuideAttentionMask` (`model.py:1230-1322` returns None), so
     the transformer blocks see plain attention over more tokens.
   - **Signatures**: unanchored A/B (chunk 0, resets) + guided A/B = **4 per route**, the same count as 114
     (whose anchored pair differed from the unanchored pair only by the per-token timestep). The eight-
     signature ceiling does not need to rise, and the freeze after qualification covers the stream.
   - **Memory**: guided activations +29% at 49 frames (+15% at 97) on the anchored signatures; the shared
     graph pool grows by an estimated ≈0.1 GiB against ≈1.7–2.3 GiB of margin over the 8 GiB floors.
   - **Delivery**: frame 0 is generated (the guide sits before it), so anchored chunks deliver every frame.
   - **Shipped**, because it fits the frozen-signature model. *Unverified on CPU*: whether the AV model's
     cross-attention and the graph-capture path behave with guide tokens on XPU (the gate shows it), and the
     host syncs `_process_input` adds per forward for keyframes (`x[:, grid_mask]`, `.item()`), outside the
     captured blocks.
3. **`latent`** (114) and **`frame`** (113) stay for A/B.
4. **Sharpness profile** on the decode thread for every chunk: Laplacian variance (4-neighbour, Rec.709 luma,
   float64, interior) of decoded frames 0, 1, 2, 5, 10, 24, the middle and the last, relative to the middle.
   It reads the F32 frames already on the CPU (≈1.5 MB cast to float64), so its cost is milliseconds.
   `owner_seam_view.py` tabulates and plots it (and measures it from MP4s for 113/114 runs).
5. **Launcher fault pattern** (coordinator finding): the 114 f97 server latched at 15:06:16 UTC on the
   driver's `Xe device coredump has been deleted.` line. 115 excludes `coredump has been deleted` from the
   GPU-fault match; creation lines and the devcoredump trace still latch (`CoredumpPattern` test).

Plus the naming rule: every name is `stream115-…`; the launcher refuses collisions (also `--check-only`).

## Exactness

- By construction: stage A in mixed is 114's latent stage A; stage B is 113's native conditioning on a
  frame whose bytes are hashed by the decode thread and re-verified by the consumer; the guide path is the
  pinned native node code. Shapes are fixed per mode.
- The gate (unchanged structure) compares eager vs graph replay vs repeat over three chunks with a cut:
  latents, anchor file, decode images and waveform, plus, for mixed, the frame each anchored stage B
  consumed (equal to its predecessor's decode record and capture last frame, and equal across chains).
- **Cross-checks predicted on CPU**: at 49 frames every mode's chunk 0 equals 114's (and 113's) chunk 0;
  mixed `stage_a_latent` of chunks 1 and 2 equals 114 latent's (the A-chain is shared); latent equals 114;
  frame equals 113 (`reference-114-qualification-hashes.json`, `…/continuation114-stream/reference-113-…`).

## Predictions (medians of 100 stream chunks; falsified outside the range)

- 49 mixed: period 2.7–3.1 s; `frame_wait` ≤ 0.05 s; anchored-chunk sharpness at frames 0–5 ≥ 0.9 of mid.
- 97 mixed: period 3.6–4.3 s (≤ 1.08 s of work per second of video); `frame_wait` 0.2–0.7 s.
- 49 guide: period 2.7–3.0 s; sampler buckets +5–15% vs 114; frames 0–5 ≥ 0.9 of mid.
- 49 latent: reproduces 114's dip (0.6–0.85 at frames 0–5).
- If mixed still dips at frames 0–5, the stage-A side carries it; then guide is the candidate.

## What could not be checked on CPU

Everything numerical on XPU: the gate, the seam quality and sharpness, speed, memory, the guide path under
graph capture, and the 97-frame audio shapes (114 at 97 measured them in its own run). The stage-B frame wait
under a real decode (the harness uses a fake 0.15 s decode). The CPU work: 160 tests in the 115 suite,
including a harness that drives the real `integration.Runtime` through setup, qualification, the verdict and
streaming in all four modes at both lengths, with resets, and five latching faults (repeat-chain difference,
decode failure, 97-frame geometry, a tampered mixed frame file, and the guide guards).

## Open questions for the owner

1. Mixed vs guide vs 114 latent, from `owner_seam_view.py` (sharpness table plus seam clips).
2. Guide changes delivery (no dropped frame; 49 new frames per 49-frame chunk): acceptable for the sink?
3. Audio is still unconditioned per chunk.
