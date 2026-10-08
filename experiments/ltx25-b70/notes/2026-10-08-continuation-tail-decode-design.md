# Continuation 116: can a tail decode feed the frame anchor? (design, CPU only)

*2026-10-08. Source reading, receipt mining and an MP4 sharpness profile. No GPU, no server, nothing
launched, no code changed. `S` = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115/source/`,
`K` = `/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen/backends/eager/na.py` (the na3d
backend the decode actually runs; the lane's axis router is inactive, `S/scripts/ltx_na_axis_router.py:1`).
Estimates are marked as estimates.*

## Answer in short

- **A k-latent-frame tail decode cannot reproduce the last frame exactly, and it is not even the same
  mathematics.** The LTX-2.5 video decoder is not the causal conv decoder. It is the NA diffusion decoder:
  neighbourhood attention that is non-causal in time, with windows that shift inward at the edges. The last
  pixel frame depends on **every latent frame**, 7 of 7 at 49 frames and 13 of 13 at 97. On top of that,
  this stack rounds a matrix product differently when the number of rows changes, and a shorter input
  changes the row count of every GEMM. Taking the last k latent frames therefore changes the anchor bytes
  by more than rounding. Under the owner's rules it is out.
- **Two exact alternatives exist:**
  1. **116a (recommended, scheduling only):** keep the frame anchor at both stages, as in 113. The chain
     waits only for the *video* decode. The audio decode, tensor hashing, diagnostics, record and preview
     move off the chain. Optionally, the stage-B anchor encode overlaps stage A.
     - Estimated **3.3–3.7 s per 2.04 s chunk at 49 frames** and **4.6–4.9 s per 4.04 s chunk at 97**
       (≈1.15–1.2 s of work per second of video).
     - Today's frame mode with text reuse projects to ≈4.1 s and ≈5.4 s.
  2. **116b (exact by construction, larger change):** a *cone-restricted* anchor decode. It runs exactly
     the kernel calls of the full decode that the last frame depends on, with the same shapes and the same
     input rows, and fills the skipped rows with zeros. A separate full display decode runs off the chain.
     The decode thread checks, per chunk, that the two last frames are byte-identical.
     - Estimated chain decode at 97 frames: ≈0.66 s instead of ≈1.2 s, giving ≈4.1–4.35 s per 4.04 s
       chunk (≈1.0–1.08 s/s).
     - At 49 frames the saving is small (≈0.15 s).
- **The softness is not a model fade-in.** Unanchored chunks are sharp from frame 0. Over frames 0–12 they
  measure 1.01–1.17 of mid-chunk at 49 frames and 0.93–1.01 at 97. The 113 frame-anchored chunks are sharp
  over frames 1–12 too (0.93–1.00), not only at the pinned frame 0. The latent-side conditionings cause
  the dip.
- **A correction to the brief:** 49 pixel frames are **7** latent frames (`[1,128,7,8,8]`), and 97 are 13.
  The formula is `a*8-7` (`S/comfy/sd.py:645`).

## 1. Causality and receptive field

### Which decoder runs

- `S/comfy/sd.py:634-649` selects `CausalDiffusionVAE` when the checkpoint has
  `decoder.conv_in_x_t.weight`. The checkpoint `/mnt/fast-ai/llm-models/LTX-2.5-baseline/vae/ltx-2.5-video-vae-bf16.safetensors`
  has that key, and its embedded config is `"_class_name": "NADiffusionDecoder"`, with exactly the defaults
  of `S/comfy/ldm/lightricks/vae/na_diffusion_decoder.py:426-464`. Its header was read on CPU.
- The conv `Decoder`, `CausalConv3d`, and the "first frame special" `DepthToSpaceUpsample`
  (`causal_video_autoencoder.py:344-655`, `causal_conv3d.py:58-92`, `causal_video_autoencoder.py:852-890`)
  are **not on the decode path**.
  - Even there, `causal_decoder` defaults to False (`causal_video_autoencoder.py:1189`). The temporal
    padding would be symmetric, replicating at both ends (`causal_conv3d.py:63-71`).
  - That `VideoVAE.decode` also draws unseeded `randn_like` noise (`:1304-1307`).
  - Only its `Encoder` is used, for the anchor encode (`na_diffusion_decoder.py:481-491,511-514`).

### What the NA decoder does

`na_diffusion_decoder.py:368-423` runs in two parts.

**Stages 1–4** are NA transformer blocks at latent rate plus linear pixel-shuffle upsamples:

- Temporal kernel 3 in every stage; depths 4, 6, 4, 2 (`:316-319`).
- The leading duplicated frame is dropped only for the chunk that holds t=0 (`:279-281`, `:371-375`).
- The trailing pad replicates the last latent frame twice and crops it afterwards (`:338-340,376-387`).

**Stage 5** is 8 `DiffusionNABlock`s with a **temporal kernel of 11** over the pixel-rate context, plus
seeded noise `x_t`:

- The noise is drawn over the whole pixel volume with a generator seeded to 0 (`:405`, `:516-520`).
- It is one `x0` step (`:407-415`).

### Non-causal windows

- na3d windows are exactly `kernel` wide, centred, and shifted inward at the grid edges (`K:31-47`).
- The decoder passes no `is_causal` (`na_diffusion_decoder.py:161`), so every axis is non-causal (`K:99`).
- The last frame therefore attends to frames L-11..L-1, and its neighbours reach further back.

### Timestep conditioning is not clip-wide

- The decoder timestep is the constant buffer `linspace(1,1,1)` (`:331-335`), embedded once (`:392-393`).
- No statistic of the clip enters it.
- Norms are per token: RMSNorm (`:36-51`) and per-token `pre` (`:131-171`). Nothing normalises across
  time.
- The audio decoder has no RNG (no `randn` in `causal_audio_autoencoder.py`, `audio_vae.py` or the
  vocoders). It is independent of the video decode.

### Receptive field, computed

I ran the real `_window_bounds`/`_pick_tiles` functions (extracted from K) and propagated the last frame
backwards through the forward geometry:

| | 49 px (7 latent) | 97 px (13 latent) |
| --- | --- | --- |
| Geometry (t,h,w) at stages 1-5 | (9,8,8) (9,16,16) (17,16,16) (33,32,32) (49,64,64) | (15,8,8) (15,16,16) (29,16,16) (57,32,32) (97,64,64) |
| Stage-5 inputs the last frame needs | frames 3–48 (46 of 49) | frames 51–96 (46 of 97) |
| Stage-4 inputs | 0–26 of 33 | 24–50 of 57 |
| Stage-3 inputs | 0–16 of 17 | 8–28 of 29 |
| Stage-2 / stage-1 inputs | all 9 / all 9 | all 15 / all 15 |
| **Latent frames needed** | **all 7** | **all 13** |
| Tail starts g that keep every window in the dependency cone unchanged | g = 0 only | g = 0 only |

The latent-rate stages (10 blocks of temporal kernel 3 after the ÷8 mapping) reach the start of the clip on
their own. **Exactness needs the whole latent.** No tail of k < T latent frames gives the same mathematics.

### Byte exactness is stricter still, even with the whole cone

A proper tail differs from the full decode in four further ways:

1. **GEMM row count.** On this stack a matrix product rounds differently with its row count
   (`notes/2026-10-04-batch-row-independence-probe.md`; `notes/2026-10-04-milestone-window-baseline.md`).
   - Stages 1–3 run each Linear over the whole sequence in one chunk: QKV chunk 256/128/256 frames, MLP
     chunk 1024/256/256 (`:145,187`).
   - So any shorter input changes M.
2. **RoPE positions.** Positions are 0-based per call: `_rope_tables` builds `arange(t)` (`:86-93,137-138`).
   - A tail would rotate with different angles. That is the same mathematics but different bits.
3. **Noise shape.** `torch.randn(pixel_shape, generator=seed 0)` (`:405`) gives a tail different noise
   values unless the full-shape noise is drawn and sliced.
4. **na3d tiling.** It depends on the full dims (`K:50-64,107-128`). Stage 5 tiles as (13,8,16) at both
   lengths.

The best a k-frame tail could achieve is "close": an approximation with truncated context. It would need
global RoPE offsets, sliced full-shape noise and `drop_leading_frame=False`, and it would still be off by
rounding plus truncation. Its size is only measurable on the GPU. It is an output change for the owner,
and it is not recommended, because 116b reaches the same cost exactly (section 2).

### The exact route: cone-restricted replay (116b)

**Why it is exact.** On this stack:

- Each kernel call's output row depends only on that call's shape and that row's inputs. Neighbour rows
  were checked to be value-independent in the row probe, and repeat chains are byte-identical.
- So a decode that issues **the same calls with the same shapes** only for the chunks and tiles in the
  last frame's cone reproduces the last frame bit for bit.
- It fills the other rows with zeros, so masked keys stay finite. A masked score becomes
  `finfo.min` (`K:84`) either way, and exp underflows to exactly 0.

**What it keeps.** At chunk and tile granularity in stage 5 it keeps:

- 70% of the per-chunk frame work at 49 frames;
- 36% at 97 frames.

**What still runs in full:**

- stages 1–4;
- the whole-tensor GEMMs `conv_in_x_t`, `norm_out` and `conv_out` (`:390-398`), which must keep M.

**Cost of the change:**

- a private re-implementation of `forward_diff_step` and of na3d's tile loop, which is pinned source;
- a per-chunk byte check against the display decode.

## 2. Cost

### Decode time

| Measured | Value | Source |
| --- | ---: | --- |
| Video decode, 25 px (4 latent), eager, alone | 0.52 s (0.61 s in Sept.) | `notes/2026-10-06-resolution-cost-probe.md:12-16`; `notes/dispatch-bound-diagnosis-01.md:28` |
| Audio decode | 0.18–0.19 s | same |
| Video + audio, 49 px, on the chain, alone (113, last 120) | **0.953 s** | 113 receipts `decode_start→decode_done` |
| Video + audio, 49 px, decode thread beside the samplers (114/115) | 1.505–1.537 s median (p90 ≈2.0) | `decode-*.json` `timing_s.decode`, four runs |
| Video + audio, 97 px, beside the samplers (114) | 2.451 s | 114 f97 run02 |

**Contention costs about 1.6×.** The same decode takes 0.95 s alone and 1.52 s beside the samplers. The
decode is dispatch- and sync-heavy:

- na3d builds every mask from host lists, with an `int(en.max())` host read per axis per geometry group
  (`K:67-85`).
- On XPU it issues one SDPA per tile (`g_max = 1`, `K:134-137`).

**Estimates.** A linear fit to the uncontended video decode is 0.28 s + 0.0096 s per pixel frame. A
no-drop tail of k latent frames emits 8k frames:

| Latent frames decoded | Pixel frames | Video decode, alone (est.) |
| ---: | ---: | ---: |
| 3 (tail) | 24 | ≈0.51 s |
| 4 (tail) | 32 | ≈0.59 s |
| 5 (tail) | 40 | ≈0.66 s |
| 7 (full 49) | 49 | ≈0.75 s |
| 13 (full 97) | 97 | ≈1.2 s |
| 116b cone at 97 | 97 (36% of stage 5) | ≈0.66 s |
| 116b cone at 49 | 49 (70% of stage 5) | ≈0.59 s |

- A tail saves little at 49 frames because the fixed part (masks, syncs, stages 1–4 with the 2-frame
  trailing pad) dominates.
- Multiply by ≈1.6 if the decode runs beside other work.

### Memory

- Measured peak: 2.6 GiB at 25 px.
- The decoder's own estimate is small (`sd.py:643`).
- xpu:3 shows ≈14.0 GiB free before a decode (decode record `xpu3_free_before_decode`) against the
  9 GiB floor (`S/scripts/integration.py:58,214-217`). There is room for both decodes, one after the other.

### Two decodes on xpu:3 at once: no

- The B70 has one CCS, and every queue serialises into one hardware FIFO (lane memory). PyTorch threads
  also share the device's default stream.
- A second decode therefore queues behind the first, and Python dispatch contention adds to that (the
  1.6× above).
- **Sequence the work on the decode thread instead:** anchor decode, then the next chunk's anchor encodes,
  then the display decode, audio and hashing.

### Sampler cards: no

- xpu:0 and xpu:1 keep only 1.7–2.3 GiB above their 8 GiB floors (115 note).
- The decoder peak plus resident VAE weights (the 1.47 GB file) does not fit.
- xpu:2 could host a byte-exact replica (packet 91b/97 precedent). It only pays if the display decode and
  the anchor decode must overlap, and 116a does not need that.

## 3. Exactness gate for 116

**116a.** No arithmetic changes; only the order of independent work changes.

- The video decode's RNG is call-local (`na_diffusion_decoder.py:518-519`), and the audio decode is
  independent.
- Gate: eager vs replay vs repeat over three chunks with a cut. Compare latents, anchor files, images,
  waveform, and the frame each stage consumed (115 structure).
- **Plus a cross-packet check:** 116a's qualification hashes must equal the 113/115-`frame` references
  byte for byte (`…/continuation114-stream/reference-113-…`).
- Per chunk: the anchor bytes handed to the chain equal `images[last]` of that chunk's later decode
  record. The record must also add `video_done`, `audio_done` and `hashed` timestamps, which today's
  `decode` field lumps together (`integration.py:219-222,277-279`).
- **If the stage-B encode is precomputed:** in the eager qualification chain, the precomputed latent must
  equal the native `LTXVImgToVideoInplace` output (`S/comfy_extras/nodes_lt.py:152-177`; the encode at
  `:170` depends only on the image and the latent's pixel size).

**116b.** The same gate, plus:

- Per chunk, on the decode thread: the cone decode's last frame must equal the display decode's last frame
  byte for byte. A mismatch latches and halts (no retry).
- Qualification: run the cone decode in all three chains and the full decode in all three.
- A synthetic CPU harness that checks the call list: same op sequence and shapes, kept or skipped.

## 4. Expected cadence (medians; estimates where marked)

**Measured stage costs (120 anchored chunks unless noted):**

| Run | Period | Submit→sampler A | Sampler A | B-prep | Sampler B | Decode |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 113 frame, 49, no reuse | 4.625 | 0.783 | ≈1.35 (bucket 1.614) | in bucket | 1.002 incl. output node | 0.953 on chain, +0.071 anchor, +0.13 receipt |
| 114 latent 49 | 2.671 | 0.100 | 1.347 | 0.02 | 0.797 | 1.529 off chain |
| 114 latent 97 (31) | 3.208 | 0.102 | 1.636 | ≈0.06 | 1.26 | 2.451 off chain |
| 115 mixed 49 | 2.885 | 0.098 | 1.350 | 0.343 (frame→concat 0.268) | 0.796 | 1.537 off chain |
| 115 guide 49 | 3.033 | 0.102 | 1.599 | — | 0.892 | 1.505 off chain |

**The anchor VAE encode is not negligible on the chain.**

- The stage-B 256² encode plus its guard snapshots measure **0.27 s** (115 mixed `frame_ready_to_concat`).
- The stage-A 128² encode is ≈0.1–0.2 s (estimate, from 113's 0.78 s with a ≈0.6 s text encode).
- The stage-B encode can overlap stage A only if the guard's pre/post snapshots stop synchronising
  xpu:0/1. They take all four cards today (`S/scripts/conditioning_guard.py:22-23,222,242`).

**Projected cadence (all with text reuse):**

| Mode | 49 px (2.04 s new) | 97 px (4.04 s new) | Seams |
| --- | ---: | ---: | --- |
| 115 `frame` today (113 behaviour) | ≈4.1 s (2.0 s/s) | ≈5.4 s (1.34 s/s) | sharp |
| **116a**, B-encode on chain | ≈3.7 s (1.8 s/s) | ≈4.9 s (1.21 s/s) | sharp, same bytes as 113 |
| **116a**, B-encode beside stage A | ≈3.45 s (1.7 s/s) | ≈4.65 s (1.15 s/s) | same |
| **116b** (cone decode) + 116a | ≈3.3 s (1.6 s/s) | ≈4.1–4.35 s (1.0–1.08 s/s) | same |
| k=4 tail (inexact, not allowed) | ≈3.3 s | ≈4.3 s | owner's call |
| Latent / mixed / guide (measured) | 2.67 / 2.89 / 3.03 s | 3.21 s (latent) | soft |

116a at 49 frames is built from:

- submit→A: 0.25 (text reuse 0.10 + stage-A encode ≈0.15);
- sampler A 1.35, upsample 0.02;
- stage-B encode 0.27, or ≈0.03 when overlapped;
- sampler B 0.80, output node 0.05;
- video decode ≈0.75, alone and on the chain;
- hand-off 0.05, receipt 0.10, turnaround 0.05.

At 97 frames, use A 1.64, B 1.26 and a video decode of ≈1.2. The 116a and 116b rows are estimates (±15%).

## 5. If exact tail decode is out, what is on the decode path besides the VAE

Of the 0.953 s chain decode in 113 (video + audio, alone):

- **Audio decode: ≈0.19 s.** It is inside `decode_start→decode_done` (`integration.py:219-222`) but the
  anchor does not need it.
- **Video VAE: ≈0.7 s.** This includes the mask building and host syncs in na3d (`K:67-85`). It also
  includes the D2H copy and F32 cast of `[1,3,49,256,256]` (38.5 MB) and the in-place clamp
  (`sd.py:519,1295-1300`), estimated at 0.02–0.05 s.
- **After `decode_done`, still on the chain in frame mode, because the chain waits for the whole job**
  (`integration.py:685-697`, `S/scripts/stream_decode.py:108-114`):
  - SHA-256 and finiteness checks over the images and the waveform;
  - the border diagnostic, and the sharpness profile over 8 float64 frames;
  - the record's validation and fsynced write;
  - private copies for the preview writer (`integration.py:225-298`; `stream_preview.py:56-59,248-291`);
  - then the anchor rehash and fsynced anchor-file write on the prompt thread.
  - Measured in 113: 0.071 s from decode done to anchor ready, plus 0.13 s from anchor to receipt.
- **Preview MP4 writing** is already behind the decode thread. It still competes for CPU with a
  dispatch-bound decode.

Today's receipts do not split the video decode from the audio decode or from hashing. 116a must add those
timestamps.

Decoding at a cheaper setting changes bytes, so it is excluded. That includes tiling, which the native
safety contract refuses anyway, and a coarser dtype.

**Decoder graph capture** would cut the dispatch part of the decode, but it needs a bounded RoPE-table and
axis-mask cache (`notes/vae-graph-capture-blocked-01.md`, "Fourth attempt"). That is an **owner decision**
under the no-caching rule. It is the biggest remaining exact decode lever: perhaps up to half the decode,
which is not measured for this decoder.

## 6. Fade-in hypothesis

**Method:** the 4-neighbour Laplacian variance of Rec.709 luma, relative to the middle frame, decoded with
PyAV from the archived previews (the `owner_seam_view.py` measure). Medians:

| Chunks | Frames 0–12, relative to mid-chunk | Last |
| --- | --- | ---: |
| Unanchored chunk 0, 49 px (`stream114/115-s00000000`, identical in all three archives) | 1.17 1.02 1.10 1.01 1.13 1.06 1.17 1.07 1.08 1.05 1.17 1.07 1.10 | 0.90 |
| Unanchored chunk 0, 97 px (`archive-stream114-run02-f97`) | 0.98 0.94 0.93 0.95 0.97 0.96 0.97 0.98 1.00 1.00 1.00 0.99 1.01 | 0.97 |
| Ten independent 25-px fixture clips (`f100b-…-timed`) | 1.07 0.89 0.90 0.89 1.01 0.97 0.96 0.95 0.99 0.89 0.91 0.91 1.00 | 0.93 |
| 113 frame-anchored (20) | 0.97 0.93 0.94 0.95 0.98 0.96 0.99 0.97 1.00 0.97 0.98 0.97 1.02 | 0.94 |
| 114 latent-anchored, 49 (20) | 0.63 0.63 0.67 0.72 0.79 0.80 0.81 0.83 0.86 0.77 0.79 0.81 0.90 | 0.90 |
| 115 mixed (20) | 0.70 0.68 0.72 0.73 0.82 0.79 0.84 0.85 0.97 0.84 0.88 0.90 0.99 | 0.92 |
| 115 guide (20) | 0.68 0.55 0.61 0.59 0.63 0.72 0.73 0.72 0.73 0.73 0.75 0.80 0.81 | 0.96 |

**Result: rejected.**

- An unconditioned chunk shows no early softness.
- The frame anchor keeps frames 1–12 sharp, not only the pinned frame 0.
- The mild period-4 ripple in every row comes from the decoder's ×2×2 temporal pixel shuffles.
- The anchored MP4 profiles agree with the F32 decode-record profiles.
- **Caveat:** the sample is thin. It is one prompt for the chunk-0 rows and ten fixture prompts at 25 px.

## Recommended 116 scope

1. **116a (build now, exact, scheduling only):**
   - Keep `LTX_ANCHOR=frame` semantics at both stages.
   - Release the chain after the video decode, with the anchor taken from those images.
   - Move the audio decode, hashing, diagnostics, record and preview behind it. Sequence the decode thread
     as: video decode → next chunk's encodes → audio/hash/preview.
   - Add split timestamps.
   - Make the stage-B encode overlap an option, gated on making its guard snapshot xpu:3 only.
   - Gate: 113 reference hashes plus eager/replay/repeat.
   - Launch at 97 frames (≈1.15–1.2 s/s predicted) and at 49 frames for A/B.
2. **116b (next, exact by construction):** the cone-restricted anchor decode, with a per-chunk byte check
   against the display decode. Only worth it at 97 frames (−0.5 s per chunk, estimated).
3. **Owner questions:**
   - Allow a bounded decoder RoPE/mask cache for decoder graph capture?
   - Or accept a non-exact tail anchor? Not recommended: 116b gets the same cost exactly.

## Open risks

- The 0.75 s alone-on-the-chain video decode is extrapolated. The preview writer and the moved audio
  decode may still contend for the CPU (114 showed 1.6×).
- The stage-B encode overlap depends on a guard redesign. Today's synchronised four-card snapshot would
  serialise it behind stage A.
- 116b relies on per-call value-independence of GEMM rows and SDPA rows on XPU. That was checked for the
  transformer's GEMMs, not for the decoder's SDPA tiles. The per-chunk byte check would catch a failure,
  but only after the next chunk has used the anchor (latch and halt).
- 116b modifies pinned decoder code paths: a new private re-implementation and an identity pin.
- The fade-in check covers few distinct prompts.
- No GPU measurement backs any cadence here.
