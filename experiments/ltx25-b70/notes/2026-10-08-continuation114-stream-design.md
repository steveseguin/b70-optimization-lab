# Continuation 114: latent anchor, decode off the chain, 97-frame chunks (built, not launched)

*2026-10-08. CPU only: no GPU, no server, nothing launched. The specification is
`notes/2026-10-08-continuation-latent-anchor-design.md` (its "Recommended packet 114
scope" and preregistration). Sources and tests:
`recovery/20261008-continuation114-stream/`. Build receipt:
`data/resume-20261008/continuation114-build.json`.*

## What 114 is

Packet 114 is packet 113 with four changes. The owner delegated the choices; the
exactness gate decides whether it streams.

1. **Latent anchor (default).** The next chunk is conditioned on latents, not on
   a decoded frame. Stage A of chunk N+1 gets the last latent slot of chunk N's
   stage-A output (node 367, before the upsampler). Stage B gets the last latent
   slot of chunk N's stage-B output (node 369), pinned again after the upsampler
   as today. The server copies each slice into slot 0 and sets that slot's mask
   to 0. That is the native conditioning node's own code after its VAE encode
   (`nodes_lt.py:156,172-175`), without the encode. A test runs the sealed native
   method on a stub VAE whose encode returns the anchor, and our copy matches it
   bit for bit. The old decoded-frame anchor stays as a launch option
   (`LTX_ANCHOR=frame`) so an A/B exists.
2. **The decode leaves the chain.** The graph no longer has decoder nodes. The
   output node hashes the three latents, writes one 40,960-byte anchor file, marks
   "anchor ready" and commits the receipt. One ordered thread then decodes on
   xpu:3, using the same native decode calls, writes the qualification capture,
   commits a decode record, and hands the MP4 to 113's preview writer behind it.
   With the frame anchor, the chain waits for its own decode (it needs the frame),
   so the frame-anchor A/B runs the decode through the same code on the same
   thread.
3. **Chunk length at launch:** 49 or 97 frames. At 97, stage A has 208 tokens and
   stage B 832. The audio shapes at 97 come from the sealed formulas, not from a
   measurement: 101 audio latents and 192,480 samples. The two measured lengths
   (49 and 25) fit the same formula exactly. The first eager chunk checks them
   and records `stream-geometry-measured.json`. A mismatch writes the measured
   shapes and halts before any stream chunk.
4. **Text reuse on by default.** It qualified exact on the live 113 server. It is
   also re-qualified inside 114's own gate (graph and repeat chunk 1 reuse).

Plus the naming rule from the 113 incident: every name starts with `stream114-`.
The launcher refuses to start if any setup or qualification name, or any
`stream114-` entry, already exists under `output/`, `output/validation/` or
`requests/`. It checks this in `--check-only` too.

## What is exact by construction, and what the gate must show

- **By construction:** the slot copy, the mask, the token counts and the graph
  shapes are the same as 113 at the same length. With the frame anchor, the model
  graph is 113's node for node; a test strips labels and compares. The decode code
  is unchanged; only its thread and timing change.
- **Needs the gate:** everything else, because the latent anchor is new output.
  The eager chain, the graph-replay chain and the exact repeat each run three
  chunks, with a prompt cut at chunk 2. Every tensor must be byte-identical per
  chunk:
  - the three latents (video, audio, stage A);
  - the anchor file;
  - the decode thread's images and waveform.

  The capture files are re-read and must agree with both the output node and the
  decode thread. The slot-0 pin (output slot 0 equals the anchor, or differs only
  by a −0.0/+0.0 sign) is recorded per chunk and never gated.
- **Where the decode overlaps:** before every gated request (the eager and graph
  chains), the decode thread is drained. Those requests may capture sampler or
  text graphs, and nothing should run beside a capture. The repeat chain uses the
  streaming form and overlaps freely. So the gate compares overlapped chunks
  (repeat) with non-overlapped controls (eager, graph), and byte equality is direct
  evidence that the overlap changes nothing.
- **Cross-check against 113:** run 114 at 49 frames, two-way20-28. Every unanchored
  chunk 0 should have byte-identical images, latents and waveform to 113's
  `stream112-qeager-c000000`. With the frame anchor, all three chunks should match
  113's. The reference hashes are in
  `recovery/20261008-continuation114-stream/reference-113-qualification-hashes.json`.
  A mismatch there would mean the moved decode is not the same computation.

## Two thread-safety problems found and closed on CPU

- **The model registry.** ComfyUI's `load_models_gpu`, which `VAE.decode` calls,
  pops the already loaded VAE from `current_loaded_models`, reloads it and
  re-inserts it. The prompt thread's residency snapshots read that list. Run at
  the same time, a snapshot could see the VAE missing and latch, or two loads could
  interleave their index arithmetic.

  114 wraps `load_models_gpu` and the adapter's inspection in one re-entrant lock
  (`stream_decode.RegistryLock`), installed before preparation. It orders
  bookkeeping only; numerics are untouched. The wrapper sits on the module
  attribute, and no sealed module imports the function by name (grepped).
- **Eviction between requests.** 113's no-eviction guard is scoped to a request.
  A 114 decode can run between requests. So the decode thread checks the packet's
  9 GiB xpu:3 floor before every decode. Below it, the decode refuses and the
  server latches, instead of letting ComfyUI evict.

The decode thread never takes the authority lock: a test walks the code to check
this. Its failures reach the authority through a separate thread, as 113's
preview writer does. The qualification captures are written by the decode
thread. The capture guard's callback is bound to that thread and still admits
exactly the nine registered rows, in order, once each.

## What is not in 114

- **Overlapping chunk N+1's stage A with chunk N's stage B across the two
  sampler cards.** This is the 1.6–1.7 s/chunk idea, and it is not a contained
  change:
  - Both stages run every forward across both cards: blocks 0–19 on xpu:0 and
    20–47 on xpu:1.
  - The overlap therefore means interleaving two chunks block by block (the
    two-clip "design B"), with two prompts in flight.
  - It also needs graph routes that today hold graphs for one prompt-executor
    thread only, and a new authority.

  This is packet 115 work, together with encode-ahead (a contract change).
- Decoder capture (not useful once the decode is off the chain), the L2 guide
  pre-roll (only if the L1 seam fails the owner look), and two chains.

## Predictions (the specification's, falsified on the median of 100 stream chunks)

- **49 frames, latent anchor:** start-to-start period 3.2–3.8 s. Sampler-A bucket
  (344→368) at most 1.65 s.
- **97 frames, latent anchor:** period 3.6–4.8 s, which is at most 1.2 s of work
  per second of video.
- **Decode record** at most 2.5 s after `anchor_ready` at 97 frames
  (`timing_s.anchor_ready_to_decode_done` in the decode record).
- **GIL cost of the overlap:** sampler-A and sampler-B buckets with the decode
  overlapping (`decode_at_start.pending > 0`) are at most 10% above the
  qualification eager and graph chunks, where it is drained. A larger rise means
  GIL contention, and decoder capture moves up the list.
- **Frame anchor at 49** costs about 113's period (4.4–4.7 s). This is the A/B
  control for speed, not just for the seam.

The receipt now splits the old sampler-A bucket at 367, 348, the stage-B
condition node and 340. That shows where the about 0.8 s of glue goes.

## What could not be checked on CPU

- Everything numerical: whether the gate passes, the seam, speed, GIL contention,
  memory at 97 frames, and the 97-frame audio shapes.
- That direct calls to `VAEDecode().decode` and `LTXVAudioVAEDecode.execute` from
  a worker thread behave on XPU as they do on the prompt thread. 113's native
  conditioning used the same direct-call pattern on the prompt thread.
- That the B70 driver is happy with eager decode kernels on xpu:3 while the text
  shard replays captured graphs on the same card. This is the same card and the
  same queue type as 113's text shard plus decode, but 113 never ran them at the
  same time.

The CPU harness (`harness_runtime.py`, run by `test_runtime_flow.py`) drives the
real runtime through setup, qualification, the verdict and streaming, in both
anchor modes, at both lengths, with a reset. Its decoder and samplers are fake,
and it shows the three faults latch:
- a one-element difference in the repeat chain;
- a decode failure;
- a wrong 97-frame audio length.

## Open questions for the owner

1. The seam with the latent anchor is out of the training distribution: an
   8-frame motion group sits in the single-frame slot. Whether it looks right is
   the owner's call, from the side-by-side in LAUNCH.md.
2. Audio is still unconditioned per chunk, with no trim rule.
3. Whether to launch at 97 directly, or first at 49 (latent and frame) for the
   A/B, then 97.
