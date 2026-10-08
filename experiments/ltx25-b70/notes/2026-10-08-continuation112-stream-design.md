# Continuation 112: a streaming continuation server with graph replay (built, not launched)

**Outcome.** Packet 112 is built and sealed at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112`
(manifest `e49f669d…52b91`, 111,971,892 bytes). It turns 111's fixed
eight-request native reference into an open-ended stream server at 256×256:

- 49 frames per chunk by default (2.04 s), with 25 frames available as a launch
  option.
- 24 fps, BF16, 8+3 steps, one sampler worker.
- Per-block graph replay: `LTXGraphCaptureGate`, all 48 blocks, chain 1, lean
  memo off.

63 CPU tests pass, and the sealed launcher's inactive `--check-only` passes. No
GPU request has been made, so nothing here shows that replay is exact, fast or
good-looking.

**One blocker to decide before launch.** The brief asks for the 256² lane's
placement, `two-way` (23/25), and also keeps the preregistered 8 GiB free-memory
floor on xpu:0. Packet 96/97 measurements put xpu:0 at about 7.5–8.1 GiB free
with that placement. The server would most likely refuse early in qualification
(cleanly, with a latch). Placement is now a launch parameter. `two-way20-28`, the
111 placement, should clear the floors by about 2 GiB. Keeping `two-way` needs
the owner to approve a lower 256² xpu:0 floor, and that needs a rebuild.
LAUNCH.md §0 has the numbers.

## What it does

1. **Setup.** The server runs the 111 text-window probe, then full residency.
2. **Qualification, before any streaming.** It runs three three-chunk chains: an
   eager chain (gate `original`), a graph-replay chain (gate `graph`, which
   installs the 48 routes), and an exact repeat in the streaming graph form.
   Every chain conditions on its own predecessor's last frame. Chunk 2 of each
   chain is a prompt cut. All nine chunks write full captures (bounded at
   356.7 MB for 49 frames). The verdict passes only if all four tensors are
   byte-identical per chunk across all three chains. That is checked twice: by
   the output node's hashes and by re-reading the capture files. It also
   requires that the anchors chain correctly and that replay-only requests
   capture nothing. A pass freezes captures and records every route's signature
   set. A failure latches the server, and it refuses all streaming.
3. **Streaming is one anchor chain.** `stream_seq` 0 is the only unanchored
   (text-to-video) chunk. Every later chunk must name the SHA-256 of the
   previous chunk's anchor, its last decoded F32 frame (786,432 bytes). The
   client never sends pixels. The anchor is conditioned through the native
   image-conditioning node at strength 1, before both samplers. Stage B is
   re-anchored after the upsampler, as in 111.
   - The prompt may change at any chunk. A cut is just a new prompt on the same
     chain, so the picture flows through it.
   - `scene_id` is a client label only. This follows the owner's change from
     the original per-scene design.
   - Gaps, repeats, stale anchors, malformed graphs and wrong text-reuse flags
     are refused before queueing, with HTTP 409 and no latch. Anything that
     fails inside an admitted request latches the server.
4. **Per-chunk receipt.** Each chunk writes `receipts/receipt-<run_name>.json`.
   It holds the four tensor hashes, anchor in and out, the preview MP4 path
   (the pipeline-save writer's format) and timing. The timing runs from submit
   through the stage-A sampler start and decode end to the preview being
   written. `timing_s.submit_to_preview_written` is the stream lag the owner
   asked for.
   - Streaming writes no capture, no gate report and no per-request state dump.
     Per chunk it writes one 786 KB anchor (only the two newest are kept), one
     MP4 and about 25 KB of JSON.
   - Each continuation chunk's frame 0 re-renders the anchor. The client must
     drop it, so a chunk delivers 48 new frames at 49, or 24 at 25.

## Candidate safety contract

The 111 native checks require zero sampler routes, so `candidate_safety.py`
subclasses `NativeReferenceSafety` and `NativeAdapter` instead of editing them.
The subclasses accept exactly this route inventory:

- The pinned installation: all48, chain 1, on the resident model.
- 48 `GraphBlockRoute`s in the gate's own route list, with each original route
  preserved.
- Devices and primaries matching the launched placement.
- Graphs held only by the prompt-executor thread, which is bound at the first
  request.
- Shared pools and groups only on (xpu:0 or xpu:1, that thread).
- At most 8 signatures per route, uniform across routes.
- After the freeze, exactly the frozen signature digests.

Everything else is inherited unchanged: residency and ownership fingerprints,
the 8/8/2/9 and 2 GiB floors (also around both conditioning stages), the
VAE-OOM refusal and the failure latches.

The conditioning guard, the bindings and the anchor helper are derived from the
sealed 111 files by anchored text replacements (`derive_from_111.py`). The
replacements change only geometry, the removed four-request bound, and the
controller class they accept.

## Text reuse (`LTX_STREAM_TEXT_REUSE`, default 0)

Within an unchanged prompt, the source supports bit-identical reuse:

- The encode has no RNG and no dropout.
- The text shard is a whole-layer pipeline split with no all-reduce, and strict
  determinism is enforced.
- Window-graph replay was proven equal to eager at capture.
- No downstream node writes into the conditioning tensor.
- 111's probe gave one identical window hash across both workers and repeat
  passes, and all six 111 chunk encodes shared a fingerprint.

So bit-identity **holds on the condition** that the cached tensor is the same
window encode (same bucket) and is served as a copy. The implementation does
both, and hashes every served tensor against the cached hashes.

It is not free under the old wording: 111's contract said "nothing is cached".
If the owner sets `1`, the qualification proves it directly. The eager chain
always encodes fresh, while the graph and repeat chains reuse at chunk 1, and
all four output tensors and the conditioning hashes must match per chunk. With
`0`, every chunk re-encodes, and receipts still record full conditioning hashes
as evidence.

## What could not be verified on CPU

- That the gate, the native samplers and the masked conditioning actually replay
  bit-exactly, and how many signatures masking adds (4 expected, 8 is the hard
  ceiling).
- Real free memory at two-way or 20/28, and the graph-pool cost at 49 frames.
- Text-window bucket of the cut prompt (assumed 64 like the boat prompt).
- That `send_sync` events give the stage timings, the preview MP4 size, and the
  real per-chunk latency.
- Whether ComfyUI's validator accepts the new nodes exactly as declared. A test
  checks that every emitted input matches the declarations, but no server ran.

## Risks

- **Masked-input capture identity.** Conditioned chunks feed a denoise mask
  into the timesteps. The signature binds shapes, types and scalars, not tensor
  values, and values are copied into static buffers on every forward. Two things
  remain unknown: whether masked and unmasked forwards produce distinct
  signatures, and whether any value-dependent path hides inside a captured
  block. The gate's three-chain, all-four-tensor equality (including a prompt
  cut) is the only defence, and it covers only these prompts and seeds.
- **Stage-B mask dropped by the upsampler.** `LTXVLatentUpsampler` removes
  `noise_mask`, so stage B is re-conditioned explicitly. The guard requires the
  stage-B input to arrive without a mask and the output to carry a fresh
  `[1,1,T,1,1]` mask. A future upsampler change would break this loudly, not
  silently.
- **Decoder anchor round-trip.** The anchor is the decoded F32 frame, which is
  re-encoded by the VAE. Over a long stream the decode→encode cycle repeats
  every chunk. It is deterministic but not identity, and drift or colour shift
  in the picture over many chunks is untested. The first boundaries need a
  human look.
- **Frozen windows.** A prompt in a different text-window bucket would change
  the context length and hit an unseen block signature after the freeze. The
  server refuses such prompts up front (`window-not-qualified`, no latch).
  Clients need short prompts (bucket 64).
- **Gate-less stream graphs.** Once installed, the routes live on the resident
  patcher, so streaming graphs omit both gate nodes, which saves about 0.4 MB of
  reports per chunk. The repeat chain uses exactly that form, so qualification
  covers it.
- **Memory and storage.** The xpu:0 floor is described above. Storage is
  bounded at 3 GiB net against a 50 GiB reserve, which is several thousand
  chunks. When it runs out the server latches.
- **Audio.** A 49-frame chunk carries 96,480 samples (2.01 s) against 2.04 s of
  video. There is still no alignment rule.

## Open questions for the owner or coordinator

1. Placement: launch `two-way20-28`, or approve a lower 256² xpu:0 floor for
   `two-way`?
2. `LTX_STREAM_TEXT_REUSE`: keep 0, or qualify 1?
3. Decode replica on xpu:2. The 97 replica path is run-behind and needs pipeline
   sentries, which conflicts with serial anchoring, so this packet decodes
   natively on xpu:3 with zero replicas and keeps only the 97 environment. Is
   that acceptable, or should a serial replica decode be designed and
   qualified?
4. The chunk 2 cut prompt used in qualification (`QUALIFICATION_CUT_PROMPT`):
   is it acceptable?
5. Preview retention: may the stream client delete consumed MP4s to extend the
   storage allowance?
6. AV timeline policy for concatenating chunk audio.

Sources: `recovery/20261008-continuation112-stream/` (code, tests, CONTRACT.md,
LAUNCH.md), build receipt `data/resume-20261008/continuation112-build.json`.
