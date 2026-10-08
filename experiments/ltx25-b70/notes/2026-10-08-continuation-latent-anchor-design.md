# Continuation after 113: latent anchors, longer chunks, two chains (design, CPU only)

*2026-10-08. Source reading only. No GPU, no server, no build. Every timing
below that is not a measured 113 median is an estimate and is marked as one.*

`S` below means the sealed 113 source tree,
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/source/`.
The 113 timings are medians of the last 301 chunk receipts of the 113 run, now
stored in `…/encoder-server-continuation-stream-113-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49.run01-20261008T0907Z/receipts/`.

## Summary

- **Today (113):** one chunk every **4.63 s** (start to start) for **2.0 s** of new
  video (48 new frames). That is **2.31 s of work per second of video**. The
  breakdown is: text and stage-A prep 0.78 s, sampler-A bucket 1.61 s,
  sampler-B bucket 1.00 s, decode 0.95 s, anchor 0.07 s, then about 0.2 s of
  receipt and turnaround.
- **The cheapest large win is longer chunks.** The transformer pays a fixed cost
  per forward to read its weights (about 0.118 s), and a chunk always runs 11
  forwards, whatever its length. At 256×256 the token-dependent part is small.
  So 97 frames should cost well under twice 49 frames. Estimate: about
  **1.5 s/s** with today's pixel anchor.
- **Latent anchoring removes the decode from the chain.** The next chunk would
  be conditioned on the previous chunk's final latent instead of its decoded
  frame. Then the decode (0.95 s at 49 frames, about 1.8 s at 97 frames) and
  both conditioning VAE encodes leave the critical path. The native
  conditioning node already accepts this: after its VAE encode it only copies
  the latent into slot 0 and sets that slot's mask to 0 (`S/comfy_extras/nodes_lt.py:170-175`).
  Shapes do not change, so the 113 graph signatures still apply. This **changes
  the output** (see "What the viewer sees"), so it is the owner's call.
- **Together they are close to real time.** 97-frame chunks, a latent anchor,
  decode behind the chain, and the text encode off the chain are estimated at
  about **0.9 s of work per second of video** (±25%). That is a little faster
  than real time.
- **At 49 frames, real time is out of reach on one chain at batch 1.** The 11
  weight reads alone are 1.3 s, plus about 0.5 s of token work and about 0.8 s
  of glue, against a 2.0 s budget. Only cross-card overlap could close that,
  and only latent anchoring makes the overlap possible (see 5).
- **Recommended packet 114:** latent anchoring with decode behind the chain,
  with the chunk length chosen at launch from {49, 97}, launched at 97, with
  text reuse kept as an owner flag (off). Preregistration sketch at the end.

## Corrections to the brief's premises

1. **A RoPE cache alone does not make the decoder capturable.** The native
   decode path also calls `comfy_kitchen.na3d`. Its eager backend builds the
   neighbourhood masks from host lists on every call:
   `torch.tensor(starts/ends, device=…)` plus a host read
   `int(en.max())`, at `/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen/backends/eager/na.py:74-76`.
   The lane's own router describes itself as "Kitchen eager routing"
   (`S/scripts/ltx_na_axis_router.py:1`). *Unverified:* that the eager backend
   is the one dispatched on XPU in 113. The decoder also draws `x_t` from a
   fresh generator on every decode (`S/comfy/ldm/lightricks/vae/na_diffusion_decoder.py:405,516-520`).
   The fourth capture attempt also found the output buffer was allocated inside
   the capture (`notes/vae-graph-capture-blocked-01.md`, "Fourth attempt").
   So decoder capture needs at least two bounded caches (RoPE frequencies and
   NA axis masks), capture of only the two pure sub-forwards, and an output
   buffer outside the capture.
2. **Text reuse would only save on chunks that keep the prompt.** In the last
   301 receipts, 75 changed the prompt (`prompt_changed`), which is one chunk in
   four. Reuse saves about 0.6 s on the other 75%.
3. **Encode-ahead already exists but has nothing to run on.** The pipeline text
   node encodes the next queued prompt on a worker thread
   (`S/scripts/pipeline_node.py:1-16`). The stream contract allows only one
   request queued or running at a time
   (`recovery/20261008-continuation113-stream/CONTRACT.md:95-97`), so
   encode-ahead never finds a next prompt.

---

## 1. Latent-space anchoring with the decode off the critical path

### What the native conditioning node actually does

`LTXVImgToVideoInplace.execute` (`S/comfy_extras/nodes_lt.py:152-177`):

1. Clones the latent (`:156`).
2. Resizes the image to the latent's pixel size if needed, using bilinear with a
   centre crop (`:165-168`). Stage A therefore encodes a 128×128 resize of the
   256×256 anchor.
3. VAE-encodes one frame (`:170`). One pixel frame gives one latent frame.
4. Writes the result into the latent's leading slot: `samples[:, :, :1] = t` (`:172`).
5. Sets that slot's mask to `1 - strength = 0` (`:174-175`). `get_noise_mask`
   (`:219-232`) supplies an all-ones `[1,1,T,1,1]` mask when the input latent
   has none.

**After the encode, step 4 is a plain copy.** Feeding a latent and skipping the
encode is the same function with step 3 replaced by "take this
`[1,128,1,h,w]` tensor". It needs no new model path and changes no shape or
mask layout. The sampler graph signatures are therefore the same as 113's at
the same chunk length.

The 113 node cannot be reused as it stands, for two reasons:

- The stage guard pins the native node and VAE sources by SHA-256
  (`S/scripts/conditioning_guard.py:13-16`).
- It requires an image anchor, an encoder-cache check and the encode workspace
  receipt (`:126-146,200-213,221-222`).

114 needs its own small node and guard: about 40 lines for the node, plus a
simpler guard.

### What the sampler does with slot 0

- The mask becomes a per-token timestep of 0 for slot 0 (`S/comfy/model_base.py:1233-1241`).
- At every step the sampler blends the model output back to the pinned latent:
  `out*mask + latent_image*(1-mask)` (`S/comfy/samplers.py:638-642`).
- The last euler-ancestral step returns `denoised` (`S/comfy/k_diffusion/sampling.py:253-254`).

So the sampler's output slot 0 equals the anchor latent.

**CPU probe of that blend** (numpy float32, IEEE semantics):

- It is bit-exact for normal values.
- A `-0.0` anchor element comes back as `+0.0`.
- A non-finite model output at that slot gives NaN.

This is the same in 113. So the pin is **exact by construction up to signed
zero**. 114 should record a per-chunk check that output slot 0 equals the
anchor bytes, or that differing elements are both zero. It is a diagnostic,
not a gate.

### Anchor latents for the two stages

- **Stage B (256×256, latent 8×8):** use slot 6 of chunk N's stage-B output
  (node 369 `video_latent`, shape `[1,128,7,8,8]`). Take the slice `[:, :, 6:7]`
  (32,768 bytes F32).
- **Stage A (128×128, latent 4×4):** use slot 6 of chunk N's **stage-A output**
  (node 367 `video_latent`, before the upsampler), slice `[:, :, 6:7]`
  (8,192 bytes).

Two alternatives are rejected:

- *Downsample the stage-B latent:* the upsampler is a learned model with no
  inverse, so pooling a latent has no basis.
- *Encode a 128² resize of the decoded frame, as today:* that needs the decode
  and defeats the purpose.

Using chunk N's own stage-A latent as the stage-A anchor creates an "A-chain"
that does not depend on stage B. Chunk N+1's stage A can start as soon as chunk
N's stage A is done. That is the only route to cross-card overlap on one chain
(see 5).

**The upsampler drops the mask.** It pops `noise_mask` (`S/comfy_extras/nodes_lt_upsampler.py:62`),
so stage B must re-pin slot 0 after it, exactly as 111 and 113 do today
(stage-B condition node on node 348's output). With a latent anchor, slot 0 of
the upsampled latent is replaced by chunk N's stage-B slot 6. Upsampling chunk
N+1's stage-A slot 0 gives something close to the B anchor, but not equal to
it. That is the same kind of mismatch as today's "encode at 256²" versus
"upsampled encode at 128²". Stage B starts at sigma 0.85 and has room to
reconcile it.

### Why the anchor is not the same kind of latent the model trained on (risk)

The video VAE is causal in time.

- The encoder handles the first pixel frame on its own (`S/comfy/ldm/lightricks/vae/causal_video_autoencoder.py:293`).
- Every temporal downsample duplicates the first frame for padding (`:776-779`).
- So latent slot 0 of an encoded clip is "one frame, as if held still". Slots
  1–6 each cover 8 moving frames: slot k covers pixel frames 8k−7…8k, and slot
  6 covers frames 41–48. The model's positions say the same: the patchifier
  maps slot 0 to pixel frame 0 with `causal_fix` (`S/comfy/ldm/lightricks/symmetric_patchifier.py:9-29`).

Today's anchor is an encoded single frame, which is in distribution. **A slot-6
latent placed in slot 0 is an 8-frame motion group in the single-frame slot.**
That is out of the image-to-video training distribution. It might carry motion
across the seam, which is good. It might also blur or pop the first frames.
*Unverified, and it needs the owner's eyes.*

**Fallback with the right meaning (variant L2).** The native latent guide,
`LTXVAddLatentGuide` (`S/comfy_extras/nodes_lt.py:525-646`), is described as
pinning "an already-encoded latent … without the VAE decode/encode round trip"
(`:531-534`). It appends the guide as extra keyframe tokens at a latent index,
and a negative index places it before the chunk (`:625-628`, `:556`). With the
last two latents (slots 5–6) at index −2:

- `causal_fix` becomes false (`:355-356`), so the guide gets group positions
  at frames −16…−1.
- The new chunk's frame 0 is generated, not pinned, so there is no duplicate
  frame to drop: 49 new frames.
- `LTXVCropGuides` (`:649-690`) removes the guide tokens before decode.

The costs:

- 128 extra stage-B tokens (448 → 576) and 32 extra stage-A tokens.
- New graph signatures.
- The attention goes through `GuideAttentionMask` (`S/comfy/ldm/lightricks/model.py:486-487`).
  *Unverified:* whether that path captures and performs like the plain one.

Keep L2 as the fallback if the L1 seam looks wrong.

### What the viewer sees at the seam

- **113 today.** Chunk N+1's frame 0 decodes the encoded copy of chunk N's
  decoded frame 48, a pixel round trip. The client drops it and plays frames
  1–48.
- **L1.** Chunk N+1's slot 0 is the latent that chunk N decoded into frames
  41–48. At the time origin the decoder keeps only the last sub-frame: each 2×
  temporal pixel shuffle drops its leading frame
  (`S/comfy/ldm/lightricks/vae/na_diffusion_decoder.py:279-282`, temporal
  strides at `:319`). So frame 0 should look roughly like chunk N's frame 48.
  It is **not** bit-identical, for two reasons:
  - The NA attention windows see different neighbours. Chunk N decodes slot 6
    with slots 4–5 and a padded tail (`:340,378`); chunk N+1 decodes it as the
    origin.
  - The decoder's noise `x_t` is drawn for the whole call shape from seed 0
    (`:405,519`).

  Keep dropping frame 0. The delivery rule stays at 48 new frames. Whether
  frame 48 of N flows into frame 1 of N+1 is up to the model. *Unverified.*
- **The colour halo.** The border/centre chroma ratio is flat along 113's
  chain but persistent. One candidate cause is the decode→encode round trip,
  which L1 removes. *Hypothesis only.* Keep the 113 diagnostic, computed on
  the decoded frame 48 in the decode record, so 113 and 114 can be compared.
- **Audio** is still unconditioned per chunk (node 366 is empty every chunk),
  so the audio seams are unchanged.

### The decode leaves the chain

The next chunk now needs only two small latents. The output node can do
everything the chain needs and then hand the decode to one ordered worker:

1. Hash `video_latent`, `audio_latent` and the stage-A latent.
2. Write and fsync one 40,960-byte latent anchor file.
3. Stamp `anchor_ready`.

The worker runs the video and audio decode on xpu:3, the MP4 and the halo
diagnostic, then commits a **decode record**. It is the same pattern as 113's
preview writer (one thread, bounded FIFO with blocking submit, private CPU
copies, a latching failure; `notes/2026-10-08-continuation113-stream-design.md`),
with the decode added. The 112 note rejected run-behind decode because it
conflicted with serial *pixel* anchoring. That conflict goes away once the
chain does not need the pixels.

Risks:

- **GIL contention.** An eager decode is CPU-bound: 0.97–1.33 core-seconds
  per wall second (`notes/vae-graph-capture-blocked-01.md:9-10`). Under the
  three-stage pipe, 0.58 s per clip stayed un-overlapped
  (`notes/three-stage-pipeline-01.md`, ceiling table). Watch the sampler-A
  times. Decoder capture becomes useful again here, as a way to cut CPU load
  rather than latency.
- **ComfyUI model management on a worker thread.** `VAE.decode` calls
  `load_models_gpu`. Prior art is the pipeline lane's decode stage
  (`S/scripts/ltx_pipeline.py:40-46`, worker per stage). Reuse it rather than
  writing a new thread.
- **xpu:3 is shared.** It holds the text encoder's secondary shard
  (`S/scripts/ltx_text_shard.py:1-8`) and the VAEs
  (`S/scripts/host_embedding_resident_node.py:203`). Per 97-frame chunk that is
  about 1.8 s of decode plus about 0.3 s of text-shard work, against a chunk
  period of about 3.6–4.2 s, so it fits (estimate).

### Expected cost per chunk

The sampler-A bucket is the time from node 344 starting to node 368 starting.
It includes the upsampler, the stage-B conditioning encode, the guard's memory
snapshots and the AV concat. The split inside it is **not measured**, so the
encode saving is an estimate.

| 49 frames | 113 measured | 114 L1 + decode behind (estimate) |
|---|---:|---:|
| text + prep | 0.78 | 0.70 (no stage-A encode) |
| sampler-A bucket | 1.61 | 1.55 (no stage-B encode) |
| sampler-B bucket | 1.00 | 1.00 |
| decode + anchor | 1.02 | 0.03 (latent anchor write) |
| receipt + turnaround | ~0.2 | ~0.17 |
| **per chunk** | **4.63** | **≈3.45** (1.73 s/s) |
| + text off the chain | — | ≈2.85 (1.43 s/s) |

**Exact by construction:** the slot copy, the mask, the token count and the
graph shapes. The decode is unchanged; only its timing and thread change.

**Needs the eager-vs-replay gate:** the whole new chain, because it is a new
output. The gate compares three chains (eager, graph, repeat) with the decode
worker active in all three, as 113 did for its preview writer. The anchor
format and the decode on a worker thread are new, so they are covered by that
same comparison, not assumed.

## 2. Longer chunks (97 = 4.04 s, 121 = 5.04 s)

**Attention is full, not windowed.** It is `optimized_attention` over all
tokens (`S/comfy/ldm/lightricks/model.py:486-490`), with 32 heads × 128 for
video and 32 × 64 for audio (`S/comfy/ldm/lightricks/av_model.py:403-406`).
The decoder's attention is windowed (11×11×11 in stage 5,
`na_diffusion_decoder.py:318,320`), so the decode grows about linearly with
frames.

The latent has T = (F−1)/8 + 1 frames (`S/comfy_extras/nodes_lt.py:83`).

| frames | latent T | stage A video tokens (4×4) | stage B video tokens (8×8) | audio latents |
|---:|---:|---:|---:|---:|
| 49 | 7 | 112 | 448 | 51 (sealed, `S/scripts/stream_contract.py:61`) |
| 97 | 13 | 208 | 832 | ≈101 (*extrapolated*) |
| 121 | 16 | 256 | 1024 | ≈126 (*extrapolated*) |

**Cost model** (*estimate*). Under graph replay a block measured 2.74 ms at 64
tokens and 3.61 ms at 256 (`notes/2026-10-06-resolution-cost-probe.md`, "Transformer").
That gives about 0.118 s of fixed cost per forward (weight reads, 48 blocks)
plus about 0.22 ms per token per forward.

The quadratic attention term is small at these sizes. At 1,024 tokens it is
about 11 GFLOP per block, a few milliseconds per forward. The model assumes
the non-forward glue grows about 1.4–1.6× at 97–121 frames (*guess*; the
upsampler is a conv over T).

| frames | A forwards (8×) | B forwards (3×) | A+B buckets | decode (xpu:3) | pixel anchor, serial | L1 + decode behind | + text off chain |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 49 (2.0 s new) | 1.14 | 0.65 | 2.61 measured | 0.95 measured | 4.63 → **2.31 s/s** | 3.45 → 1.73 | 2.85 → 1.43 |
| 97 (4.0 s new) | 1.30 | 0.90 | ≈3.3 | ≈1.8 | ≈6.1 → **1.52 s/s** | ≈4.2 → 1.05 | ≈3.6 → **0.90** |
| 121 (5.0 s new) | 1.39 | 1.02 | ≈3.65 | ≈2.3 | ≈6.9 → **1.38 s/s** | ≈4.5 → 0.90 | ≈3.9 → **0.78** |

**Memory** (*estimate*).

- **xpu:0/1** had 9.57 / 10.1 GiB free before a chunk, against an 8 GiB
  admission floor (`S/scripts/conditioning_guard.py:18`). Per-token
  activations at 1,024 tokens are tens of MB. The shared graph pool was
  0.42 / 0.31 GiB at batch 2 with 25 frames (512 stage-B tokens;
  `notes/2026-10-05-packet-97-build.md:141`). Scaled up, that is roughly
  0.7–1.0 GiB at 832–1,024 tokens, inside the 1.5 GiB margin. Longer chunks
  replace the 49-frame signatures rather than adding to them: four per route
  today, against a cap of 8.
- **xpu:3** had 13.1 GiB free. The decode peak is about 1.6 GB above resident
  at 49 frames; ComfyUI's own estimate scales with T (`S/comfy/sd.py:643`). At
  121 frames that is about 4 GB. It fits.

**Viewer implications.**

- Fewer seams: one every 4–5 s instead of 2. That fits the owner's "longer
  scenes".
- The prompt-change granularity is the chunk length, so a cut lands 4–5 s
  after it is asked for, or one chunk more with encode-ahead queueing.
- The first frame of a chunk appears after its sampling and its decode: about
  5–6 s at 97 frames.
- If generation is at or above real time, a one-chunk buffer plus jitter gives
  no holds. If it is below, the sink holds once per chunk in proportion.

**The model's working length:** 97 and 121 are LTX's usual lengths, but that
is general knowledge, not checked against this checkpoint. The contract
allows only 25 and 49 (`S/scripts/stream_contract.py:30,95`), so 97 needs a
new geometry entry: audio latents, waveform samples and the anchor index,
each measured on the first eager chunk and then sealed.

## 3. Two interleaved chains on the two sampler cards

**What exists.** `pipeline_sampler_node.py` already overlaps two independent
clips across the block split. It runs two sampler workers, each with its own
streams and graphs (`S/scripts/pipeline_sampler_node.py:1-17`;
`S/scripts/ltx_pipeline.py:42-46`). It does this as **run-behind**: each
prompt emits the clip sampled `depth` prompts earlier. The batch path stacks B
clips into one forward (`S/scripts/ltx_sampler_batch.py:1-28`). Measured on
independent 25-frame clips: 1.308 s per clip with two jobs at batch 1, and
0.927 s at batch 2 (`notes/2026-10-06-packet-97-results.md:15-17`). The
block-GEMM probe reached 1.68× of serial with two free threads
(`notes/two-clip-sampler-design.md`, probe table).

**Why it does not carry two anchored chains as it stands:**

1. **No stage-B re-anchor.** `_sample_chain` runs 377→344→367→348→340→368→369
   as one unit, with no hook between the upsampler and stage B
   (`pipeline_sampler_node.py:596-638`). The 113 stream graph uses native
   samplers with condition nodes in between for exactly this reason.
2. **The batch path refuses masks.** It rejects any `noise_mask`
   (`ltx_sampler_batch.py:208`).
3. **Run-behind conflicts with a chain.** The anchor for chain c's chunk n is
   chain c's chunk n−1. Under run-behind, that chunk is collected inside the
   same node that must already have been conditioned on it. That needs a new
   combined "collect, condition, submit" node.
4. **The authority is one chain**, with one request in flight (`CONTRACT.md:95-97`).

The video timestep max is taken over the whole batch (`S/comfy/ldm/lightricks/av_model.py:806,812`).
That is harmless for two chains in lockstep: the mask only zeroes slot 0, so
the max is still sigma. Batch-2 rows are bit-independent of their neighbours
(`notes/2026-10-04-batch-row-independence-probe.md`), but they differ from
batch 1 by rounding, which is an output change.

**Throughput** (*estimate*, 49 frames, L1, decode behind):

- Batch 2: one pass costs about 1.4–1.6× a single chunk, about 3.7–4.2 s for
  two chunks. That is **0.5× real time per chain, about 1.0× combined**.
- Two workers: about 3.4 s per pair, so 0.6× per chain and 1.2× combined.

**Uses for a viewer:**

- *Cross-cut:* alternate A, B, A, B, each chunk continuing its own chain. The
  combined rate of about 1× gives real-time playback with a cut every chunk.
- *Two panes:* each pane is below real time and holds.
- *Next scene ready:* chain B pre-renders the next scene's opening.

All three change the product. They are the owner's call, not a speed lever
for one continuous shot. Implementation risk is the highest of the five ideas:
a new authority, a new sampler node, mask batching, and a new qualification.

## 4. Text-encode reuse and the decoder RoPE cache

**Text reuse is already built.** It is behind `LTX_STREAM_TEXT_REUSE`
(`S/scripts/integration.py:72-73`). It keeps exactly one entry, the chain's
most recent fresh encode (`:256-257`), and serves a deep copy only when the
request says `reuse_text=1` and the prompt's SHA matches (`:261-269`).

- **Why it is exact:** the encode is deterministic. 113's qualification
  passed eager vs graph vs repeat with fresh encodes on every chunk, so equal
  prompts give equal conditioning bytes, and a copy of those bytes is the
  same input.
- **What it takes:** 0 lines. It needs the owner's ruling, a launch variable,
  the client flag, and the existing reuse-against-fresh qualification.
- **Saving:** about 0.6 s on three chunks in four. That is about 0.22 s/s at
  49 frames and about 0.11 s/s at 97.

**Encode-ahead dominates reuse.** It saves the same 0.6 s on every chunk,
including cuts, and caches nothing (`S/scripts/pipeline_node.py:1-16`). It
needs a contract change: chunk N+1 is queued while chunk N runs, and its
predecessor is named by `stream_seq − 1`, with the hash bound and recorded at
execution. That also removes most of the 0.2 s turnaround. Its risk is in
admission and the authority, not in the numbers. The text graphs move to a
worker thread, so the eager-vs-replay gate must cover that. Packet 48's pipe
arm already proved encode-ahead bytewise exact.

**The decoder RoPE cache.** `rope_inv_freqs` computes `1/base^(2i/d)` in fp64
on the CPU, because the B70 has no fp64. It casts to fp32 and copies to the
device on every attention call (`na_diffusion_decoder.py:77-83,137`).

- **Why caching it is exact:** the value depends only on (`d`, `base`): Python
  numbers, a deterministic CPU computation, an exact cast and an exact copy.
  A device tensor kept from the first call holds the same bits every later
  call would build.
- **Keep only the frequencies.** The cos/sin tables (`:86-93`) can still be
  recomputed on the device every forward from the cached frequencies, so the
  arithmetic does not change.
- **Size of the cache:** the head dimension is 64, so the split is (16, 24, 24)
  (`:68-75`). That is two entries of 8 and 12 floats per device, 80 bytes.
- **Size of the code:** about 15 lines.
- **The trap:** changing `na_diffusion_decoder.py` changes the VAE source hash
  pinned at `conditioning_guard.py:16`. The sealed-literal pins must move with
  it.

As noted at the top, the cache alone is not enough: the NA mask cache, the
generator boundary and the output buffer are also needed. **After 114's decode
behind the chain, decoder capture saves no chain time.** It would only reduce
xpu:3 time and GIL pressure. Do it later, or never.

## 5. What real time (≤ 2.0 s of work per 2.0 s of video) would still need

**At 49 frames on one chain, after everything above:** about 2.85 s against
2.0 s. The floor is:

- 11 forwards × 0.118 s of weight reads = 1.30 s.
- About 0.48 s of token compute.
- About 0.8 s of glue that has not been measured.

Making block kernels faster cannot go below the weight reads. The only
candidate is **cross-card overlap inside one chain**: stage A of chunk N+1 on
one card's blocks while stage B of chunk N is on the other's. Only the L1
A-chain makes that legal, because stage A of N+1 then depends only on stage A
of N. The heavy single-scheduler design B in `notes/two-clip-sampler-design.md`
does this. With the measured 1.68× overlap, the estimate is about 1.6–1.7 s
per chunk.

**At 97 frames:** about 0.90 s/s (±25%) with L1, decode behind and the text
off the chain, so real time with a small margin, or just short. If it is
short, there are two remaining levers:

- **121 frames:** about 0.78 s/s, with seams every 5 s.
- **Measure and cut the 0.8 s of glue:** the upsampler, the guard memory
  snapshots, the AV separate/concat, and any per-step host syncs. 114 should
  add node-start events for 367, 348, the B condition node and 340, so the
  sampler-A bucket can be split.

The 8+3 step schedule and the 256×256 minimum are unchanged throughout.

**Higher resolution comes after this.** At 256² the lane is bound by weight
reads, so longer chunks are nearly free. At 512×320 there are 2.5× the tokens
and the token compute dominates, so the trade turns around. Take the length
win at 256² first.

## Ranking

The score is the saving in seconds of work per second of video, divided by
risk on a 1–5 scale. Savings are estimates against today's 2.31 s/s.

| # | lever | saving (s/s) | output change | risk | score |
|---|---|---:|---|---:|---:|
| 1 | 97-frame chunks (pixel anchor kept) | ≈0.8 | yes: length, seams | 2.5 | **0.32** |
| 2 | text reuse (built) | ≈0.22 | no | 1 | 0.22 |
| 3 | L1 latent anchor + decode behind (49 f) | ≈0.58 (≈0.45 more at 97 f) | yes: seam semantics | 3.5 | 0.17 |
| 4 | encode-ahead (contract queue-ahead) | ≈0.30 | no | 2 | 0.15 |
| 5 | decoder capture (RoPE + mask caches) | ≤0.24 if decode on chain, ≈0 after #3 | no | 4.5 | ≤0.05 |
| 6 | two chains (batch 2 or two workers) | per chain worse; combined about 2× | yes: product | 5 | — |

Levers 1 and 3 together are where real time first appears: about 1.05 s/s
before the text lever, about 0.90 s/s after it. Lever 3 is worth much more at
97 frames, because the decode it removes doubles.

## Recommended packet 114 scope

Packet 114 = **113 plus the L1 latent anchor plus decode behind the chain, with
the chunk length (49 or 97) chosen at launch, launched at 97.** Text reuse
plumbing stays as an owner flag, default off. Out of scope:

- encode-ahead (115: a contract change);
- decoder capture;
- the L2 guide pre-roll (only if L1's seam fails the owner's look);
- two chains.

Owner decisions needed before launch:

- (a) the L1 output change, after a side-by-side;
- (b) 97-frame chunks;
- (c) text reuse, if wanted in the same reload.

### Preregistration sketch (packet 114)

- **Identity.** 113's identity except as listed here: model
  `273ad912…`, `two-way20-28`, one worker, batch 1, graph replay all48, 8+3
  euler-ancestral steps, cfg 1, bf16 weights with F32 CPU intermediates,
  strict determinism. Run names get a fresh prefix (`stream114-…`), and every
  reused literal is grepped before launch (the 113 naming incident).
- **Changes.**
  1. Node `LTXStreamLatentCondition114`, stages A and B. It runs
     `nodes_lt.py:156,172-175` with `t` set to the anchor latent.
  2. A latent anchor file holding A6 `[1,128,1,4,4]` and B6 `[1,128,1,8,8]`,
     F32 little-endian, 40,960 bytes, whole-file SHA-256, verified on every
     read.
  3. Node 367's output wired to the output node.
  4. An ordered decode worker on xpu:3 that writes a decode record (images and
     waveform hashes, MP4, halo diagnostic).
  5. Geometry for 97 frames, sealed after the first eager chunk measures the
     audio shapes.
  6. Node-start events for 367, 348, the B condition node and 340.
- **Qualification (gate, at the launched length).** Eager chain vs graph chain
  vs exact repeat, three chunks each, with a prompt cut at chunk 2. Every
  tensor must be byte-identical: video and audio latents, the stage-A latent,
  both anchor latents, and the decoded images and waveform from the decode
  worker, which runs in all three chains. Diagnostic only: output slot 0
  equals the anchor bytes, or differs only in signed zeros.
- **Predictions.** Each is falsified if the median of 100 stream chunks falls
  outside its range.
  - 49 frames: start-to-start period 3.2–3.8 s; sampler-A bucket at most
    1.65 s.
  - 97 frames: period 3.6–4.8 s, which is at most 1.2 s/s.
  - Decode record at most 2.5 s after `anchor_ready` at 97 frames.
  - Sampler-A and sampler-B buckets with the decode overlapping are at most
    10% above the qualification chunks where it does not. A larger rise means
    GIL contention, and decoder capture moves up the list.
- **Owner-view set.** At 49 frames, the same ten kitten prompts and seeds,
  twenty chunks of 113 (pixel anchor) and of 114 (L1), plus twenty chunks of
  114 at 97 frames. Include the per-seam frames 48 | 1 and the halo ratio from
  the decoded frame 48. The owner decides L1 against L2 against the pixel
  anchor.
- **Stop rules.** Any eager/replay difference latches with no retry. The
  admission floors are unchanged (8 GiB free on xpu:0/1, 9 GiB on xpu:3). A
  decode queue held full for more than three chunks holds the stream; it does
  not drop chunks. A GPU fault halts new requests, with one controlled stop as
  a single incident action. There is no restart loop and no reboot. Keep the
  five-minute gap between a stop and a launch.

## Unverified items to settle first (CPU where possible)

1. Which `na3d` backend runs on XPU in 113. This only matters for decoder
   capture.
2. The 97-frame audio latent and waveform shapes: measure on the first eager
   chunk.
3. The split of the sampler-A bucket (upsampler, guard snapshots, encode).
4. The seam and drift behaviour of a group latent in slot 0: owner look.
5. GIL contention from an eager decode running behind the sampler.
6. Whether the upsampler checkpoint uses 3D convolutions, which mix time
   (`S/comfy/ldm/lightricks/latent_upsampler.py:183-210`). This affects how
   far the upsampled slot 0 drifts from the B anchor.
