# Continuation 117: the cone anchor decode, the stage-B encode beside stage A, 121-frame chunks, prep-ahead (built, not launched)

*2026-10-08. CPU only: no GPU, no server, nothing launched. Sources and tests:
`recovery/20261008-continuation117-stream/`. Build receipt: `data/resume-20261008/continuation117-build.json`.
Packet: `prepared-continuation-stream-117` (manifest in the receipt). Parent: packet 116b. Specification:
`notes/2026-10-08-continuation-tail-decode-design.md` (option 116b and the stage-B overlap) and the 116b live
measurement (`notes/2026-10-08-continuation116-stream-design.md`, 116b section). Estimates are marked as such.*

## Why

Packet 116b at 97 frames (frame anchor, decoder graph on, text reuse) runs one 4.04 s chunk every 5.54 s
(1.37 s of work per second of video). Medians of 71 anchored stream chunks from its receipts:

| on the chain | seconds |
|---|---:|
| submit → sampler A start (admission, request snapshot, anchor read, stage-A conditioning) | 0.435 |
| sampler A | 1.624 |
| upsampler | 0.036 |
| stage-B conditioning (two four-card snapshots + the 256² VAE encode) | 0.265 |
| sampler B | 1.195 |
| video decode (graph replay) | 1.572 |
| hand-off (anchor file) | 0.030 |
| anchor ready → receipt staged | 0.115 |
| receipt → next submit (commit, client turnaround) | 0.156 |
| **period** | **5.54** |

The decode is the largest item and the decoder graph removed only 0.15 s of it (eager 1.72 s): it is
compute-bound. The only sharp anchor is the decoded frame (latent-side anchors blur the first ~12 frames), so
the chain must wait for an anchor frame; 117 makes that wait shorter and takes the two anchor encodes off the
chain, without changing a byte.

## What 117 is

Packet 116b plus four launch-selectable levers (all on by default) and its own names (`stream117-`, packet
id 117). Each lever is exact by construction and gated:

1. **`LTX_ANCHOR_DECODE=cone`**: the anchor comes from a decode that computes only what the last pixel frame
   depends on; the full decode for display follows, off the chain, and must match byte for byte.
2. **`LTX_BENCODE_OVERLAP=1`**: the stage-B anchor encode runs on the decode thread beside stage A.
3. **`LTX_STREAM_FRAMES=121`**: 5.04 s chunks.
4. **`LTX_PREP_AHEAD=1`**: the stage-A anchor encode runs on the decode thread before the next request
   reaches it.

Kept from 116b: the decoder graph with its router-aware installer; the chain waiting only for the anchor
decode; `stream117-` names with the collision preflight; chain resets; the coredump-deletion exclusion;
sharpness diagnostics; the cross-packet reference (the eager chain, levers off, equals the packet-113/114
frame qualifications at 49/97 frames).

## Lever 1: the cone-restricted anchor decode

**What the last frame depends on.** Stage 5 of the NA diffusion decoder is 8 `DiffusionNABlock`s with a
temporal window of 11 frames, shifted inward at the clip's ends. Propagating the last frame back through the
eight windows (the real `na._window_bounds`; a brute-force test agrees):

| frames | stage-5 input frames the last frame needs | na3d query tiles kept | context_proj / qkv / proj / SwiGLU rows kept |
|---:|---|---:|---|
| 49 | 3–48 (46 of 49) | 62.5% | 71% / 84% / 76% / 59% |
| 97 | 51–96 (46 of 97) | 34.4% | 36% / 46% / 38% / 30% |
| 121 | 75–120 (46 of 121) | 25.8% | 31% / 37% / 34% / 26% |

(stage-5 tiles are 13×8×16 at 49/97 and 8×16×16 at 121; GEMM chunks are 16 frames for context_proj/SwiGLU
and 32 for qkv/proj; rows are counted at chunk granularity, because a call runs whole or not at all.)

**How it is built** (`stream_anchor_decode.py`). Inside a cone scope on the decode thread, the decoder's
`forward_diff_step` is replaced by `ConeStep`, a line-for-line re-implementation of the sealed
`forward_diff_step`, `DiffusionNABlock.forward`, `NeighborhoodAttention3D.forward`, `SwiGLU.forward` and of
the eager `na.na3d` tile loop that skips every chunk call and every query tile outside the cone. A call that
runs is the full step's call: the same module, the same input slice shape, the same rows. q/k/v and the na3d
output are zero-filled where nothing ran. `conv_in_x_t`, the timestep embedding, `norm_out` and `conv_out` run
on the whole tensor; stages 1–4 (`forward_pre_diffusion`, graph-replayed with dg1) and the seed-0 noise are
untouched. The anchor is `images[last]` of an otherwise native `VAEDecode` (the VAE's F32 cast and
`process_output` run unchanged). With the decoder graph the cone sits over its `forward_diff_step` shadow
(`DecoderGraph.register_outer`), and its masks and RoPE tables come from the same bounded caches, all of
which the full decode already fills.

**Why it is exact.** Every call that runs has the full step's shape and, for every row in the cone, the
full step's input bytes; on this stack an output row depends only on the call's shape and that row's inputs
(GEMM rows: the batch-row probes; norms, RoPE and elementwise ops per token; an SDPA query row: softmax and
P·V are per row, and a key outside the query's window gets the additive mask `finfo.min`, whose exponential
is exactly 0 whatever that key holds). So the last frame is the full step's last frame bit for bit. The row
count of every call that runs is the full decode's, so the "row-count rounding" objection to a tail decode
does not apply. Two cases where exactness would not hold by construction are refused: na3d not dispatched to
the eager backend (another kernel; checked at install, with 116b's router acceptance), and CUDA tile stacking
(`g_max > 1` batches several tiles into one call, whose shape a skipped tile would change; on XPU and CPU
`g_max` is 1).

**The check.** The decode thread still runs the full native decode for display and compares its last frame
with the anchor byte for byte on every chunk; a difference latches the server and writes
`anchor-decode-117-refused.json` (the launcher then refuses `cone`). The qualification capture files are
written from the display decode, so the gate's "anchor file = capture's last frame" check is an independent
second proof. A failure on a stream chunk is caught after the next chunk has consumed the anchor (latch and
halt, as the tail-decode note foresaw); in the qualification the chains wait for their whole decode, so the
gate sees it first.

**Scheduling.** The display decode must not sit in front of the next chunk's four-card snapshots, which
synchronise xpu:3 (a graph replay submits its whole 1.3 s of work at once). So the decode thread, after the
hand-off, waits (bounded 3 s) until the next chunk's sampler A has started (node 344's `executing` event),
and only then runs the display decode, while xpu:0/xpu:1 sample. At 97 frames the stage-B encode (0.1 s)
plus the display decode (1.57 s) just fill sampler A + upsampler (1.66 s); the audio decode, hashes, record
and MP4 follow during sampler B.

**Cost (estimate).** Stage 5 is about 85% of the decode (2,048 of its 2,098 SDPA calls at 97 frames). Cone
at 97: stages 1–4 replayed (≈ 0.12 s) + whole-tensor GEMMs and the F32 post-processing (≈ 0.06 s) + ≈ 38% of
stage 5 run eagerly (≈ 0.5–0.6 s) ≈ **0.65–0.95 s on the chain instead of 1.57 s**. At 121 frames: ≈ 0.70–1.0 s
instead of ≈ 1.96 s (full).

## Lever 2: the stage-B anchor encode beside stage A

**The obstacle (116b).** The conditioning guard's snapshot is the sealed `NativeReferenceSafety._snapshot`
(via `CandidateSafety`): it synchronises all four cards, and the guard is bound to the prompt thread. The
stage-B encode cannot simply move.

**The design** (`precompute_guard.py`). The encode moves to the decode thread; the four-card checks stay
where they were:

- The decode thread, when the next chunk's sampler A starts, calls the native `LTXVImgToVideoInplace.execute`
  with a `CaptureVAE` (the real `VAE.encode`, recorded once: the pixels' SHA-256 and the latent `t`) on a zero
  latent of the stage's shape. It does so between two **xpu:3-only snapshots** (`Xpu3Snapshot`) and under an
  **encoder lock** that no prompt-thread conditioning call can hold at the same time.
- The stage-B node later runs the same native node with a `ReplayVAE`, whose encode accepts exactly the
  recorded pixels (shape, dtype, SHA-256) and returns a copy of `t` (SHA-256 checked); the resize, slot copy
  and mask are the native code on the node's own inputs. This runs **inside the unchanged
  `ConditioningStageGuard.run_stage`**, with its four-card before/after snapshots.
- In the graph qualification chain the node also runs the native encode on the same inputs and requires
  both results (samples and mask) to be byte-identical; a difference latches and writes
  `precompute-117-refused.json`.

**Every check and where it runs now** (CPU-proved: `test_precompute_guard.NoCheckWeakened` drives the REAL
`CandidateSafety` and `ConditioningStageGuard` through an anchored A+B conditioning in the native and the
precomputed mode and finds the same snapshot events, the same floors, the same cards synchronised at each
snapshot, the same guard receipts and byte-identical outputs; an AST test pins that every precomputed stage
goes through `run_stage` under the encoder lock):

| check of the four-card snapshot | 116b | 117 (levers on) |
|---|---|---|
| require_phase (authority phase, active request, adapter, fault observer) | request before/after, stage A before/after, stage B before/after (prompt thread) | the same six points, unchanged; plus P1–P3 around each precomputed encode (decode thread) |
| synchronise xpu:0, xpu:1, xpu:2, xpu:3 | the same six points | unchanged; the encode guard synchronises xpu:3 (only) |
| inspect: node bindings, layout, host identity, 48-route inventory, W1 B1, text capture, window | six points | unchanged |
| residence and ownership of all seven roles | six points | unchanged; plus the three xpu:3 roles around each encode (P7) |
| both VAEs bound to the safety controller | six points | unchanged; plus P8 |
| physical free floors: 8/8/2/9 GiB before, 2 GiB after, every card | six points | unchanged; plus xpu:3 9 GiB before / 2 GiB after around each encode (P5) |
| allocation counters valid, every card | six points | unchanged; plus xpu:3 (P6) |
| anchor bytes, SHA-256, finiteness; input latent ownership; output aliasing | stage A/B (guard) | unchanged; plus E2 around each encode |
| encoder temporal cache empty (own and foreign) | stage A/B (guard) | unchanged; plus E3 around each encode, and the encoder lock (E1) makes a foreign entry impossible |

**Why not drop the stage-B snapshots' xpu:3 sync instead?** That would weaken a check (the snapshot's
`_free` synchronises every card it reads), so it was not done. The cost is that the stage-B node waits if
the display decode overruns sampler A; at 97 frames it just fits (above).

**Cost (estimate).** The stage-B node keeps its two snapshots; the 256² encode (≈ 0.09–0.12 s of the
0.265 s, from the 116b safety receipts) leaves the chain: **≈ 0.14–0.20 s** at stage B.

## Lever 3: 121-frame chunks

16 latent frames; 256/1024 video tokens; audio 126 latents and 240,480 samples from the sealed formulas
(`round(121/24·25) = 126`; `((126−1)·4+1)·480`, the formula the measured 49 and 97 lengths satisfy), checked on
the first eager chunk. New geometry entries in `stream_contract`, the geometry overlay (`ltx_output_size_98.py`)
and the capture guard (`ltx_duration_guard.py`); the output node admits up to 121 frames.

**Memory (estimate, floors are the stop rule).** xpu:0 is the tight card: the stage-B snapshot saw
10.10 GB free at 97 (1.41 GiB above the 8 GiB floor; 10.27 GB at 49), so ≈ 9.95–10.0 GB at 121 (≈ 1.3 GiB
margin). xpu:3 with the decoder graph: the pool and static buffers took ≈ 3.5 GB at 97; ×1.25 at 121 gives
≈ 11.3 GB free before a decode, 1.6 GB above its 9.66 GB floor; the cone's eager stage-5 transient (≈ 1.8 GB at
121) should reuse blocks the qualification's eager decodes reserved, but if the allocator holds it on top, the
next decode's floor refuses (a latch, no damage) and the 121 launch should then run with
`LTX_DECODER_GRAPH=0` (≈ 15.6 GB free). Captures: 9 × 97.6 MB.

**Cost (estimate).** The samplers scale with tokens (×1.23): sampler A ≈ 2.0 s, sampler B ≈ 1.47 s.

## Lever 4: prep-ahead

**What text + A-prep is made of** (116b repeat-chain chunk 1, 97 frames, from its safety receipts; submit →
sampler A 0.444 s): admission and the request's four-card snapshot ≈ 0.107 s; graph nodes, anchor read and
check, the stage-A guard's pre-checks and its before snapshot ≈ 0.144 s; the 128² encode with its resize
and the after snapshot ≈ 0.166 s; ≈ 0.03 s to the sampler.

**What moved.** The stage-A anchor encode (and its 256→128 resize) depends only on the anchor frame, so the
decode thread runs it right after the chunk's receipt commits (beside the client's turnaround and the next
request's admission), under the same xpu:3-only guard and encoder lock, and the stage-A node consumes it
through `ReplayVAE` inside the unchanged guard. **What did not move, and why.** The noise, empty latents,
sigmas and `LTXVConditioning` are ComfyUI nodes of the successor's own request that cost milliseconds; running
them earlier would need node outputs cached across requests, which the executor guard refuses (no cached
nodes). With text reuse the conditioning is already a cached copy and a hash (≈ 1.25 MB). The request's and
the stage's snapshots are safety checks at fixed points and stay. **Cost (estimate):** submit → sampler A
**≈ 0.33–0.40 s** (−0.05 to −0.10 s).

## Exactness and the gate

- **By construction:** the cone (above); the precomputed encodes (the same native node, the same `VAE.encode`
  on byte-identical pixels on the same device; the replay checks the pixels' hash); the schedule changes only
  when independent work runs.
- **CPU-proved** (sealed decoder, real eager na3d/RMS-RoPE, small widths, real kernels/upsamples/pads):
  the re-implemented stage-5 step with nothing skipped equals the sealed `forward_diff_step` byte for byte
  (fp32, bf16, many na3d tiles); the cone's last frame equals the full decode's at several lengths with
  tiles, context_proj/SwiGLU chunks and qkv/proj chunks all skipped; the cone's calls are a subsequence of the
  full step's with identical shapes; graph-mode cone = eager cone = full last frame through the decoder-graph
  controller. The sealed native `LTXVImgToVideoInplace` gives byte-identical stage-A and stage-B outputs with
  the native and the replayed encode at 49/97/121 frames. The whole runtime runs end to end on CPU fakes
  (qualification, verdict, streaming, resets) with every lever combination at 49/97/121, and each injected
  fault (cone mismatch at the graph chain or the repeat chain, a precomputed encode that differs, an xpu:3
  floor refusal) latches and writes the right latch.
- **The gate** (`qualification_gate.decide`): 116b's (every tensor byte-identical across eager / graph /
  repeat chains; the decoder graph's dual decode; the 113/114 reference at 49/97 for the eager chain, which
  runs every lever off), plus `lever_rows`: eager chain `full` and native encodes; graph and repeat chains
  `cone` with `equal` on every chunk and the anchor equal to the capture's last frame; anchored graph and
  repeat chunks conditioned from the precomputed encodes; graph chunks `dual_equal` true for both stages.
  Failures go to `anchor_decode_failures` / `precompute_failures` and write the latches.

## Predictions (medians of 100 stream chunks, frame anchor, dg1, two-way20-28, text reuse; falsified outside)

| launch | chain decode | period | work per second of video |
|---|---|---|---|
| 97, cone/1/1 | 0.65–0.95 s | **4.35–4.9 s (central 4.6)** | 1.08–1.21 |
| 121, cone/1/1 | 0.70–1.0 s | **5.2–5.8 s (central 5.35)** | 1.03–1.15 |
| 97, full/0/0 (control on 117 code) | 1.55–1.60 s | 5.4–5.7 s (= 116b) | 1.34–1.41 |

Per lever at 97 (central): cone −0.77 s, overlap −0.09 s, prep-ahead −0.08 s, from 5.54 s.

**The ≤ 4.4 s target at 97 frames is met only at the optimistic end** (a cone decode at ≈ 0.65 s). The next
lever after 117 is not the decode: it is the six four-card safety snapshots per chunk (request before/after,
stage A before/after, stage B before/after), each ≈ 0.05–0.09 s on the chain (sync of four cards + the full
residence/route inspection), ≈ 0.3–0.5 s per chunk in all. Making them cheaper without weakening them (for
example checking the residence fingerprints against the allocator's state instead of walking every
parameter) is an owner-visible safety change and is not in 117. At 121 frames the target band (≈ 1.0–1.1 s/s)
is reached by the estimate.

## What CPU cannot verify

- That the XPU kernels keep per-row independence for the stage-5 shapes (GEMM rows were probed for the
  transformer, not for the decoder; SDPA rows were never probed). The per-chunk byte check and the gate
  decide; a mismatch latches before any wrong anchor is used in qualification.
- The cone's real speed (eager stage-5 kernels under graph-replayed stages 1–4), the display decode's fit in
  the sampler-A window, and whether the stage-B snapshot then waits for it.
- xpu:3 and xpu:0 memory at 121 frames (estimates above; the floors stop the run).
- The 121-frame audio shapes (sealed formulas; checked on the first eager chunk).
- Whether `torch.xpu.synchronize('xpu:3')` from the decode thread interacts with the sampler on xpu:0/1
  (it should not: one card).
- The sampler and upsampler at 256/1024 tokens (new signatures, captured in qualification).

## Build

Packet `prepared-continuation-stream-117`, manifest `5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9`,
plan `8390d15e…55d4c4` (132 qualification ids), 118,824,767 bytes, zero `__pycache__`, source closure verified
against 116b … 111. CPU suites: 117 249/249 (incl. 24 new cone/precompute tests and 9 new runtime-flow
lever cases); 116b 197/198 (the one failure is its "live root is clean" check, true since the 116b run created
its names); client suites in the build receipt. The `--check-only` rehearsal refused at `verify_model_receipt`
on `FAULT.json` (four-card device fault at 21:11 UTC during the Flash-Next calibrate-load, owner reboot
decision pending); every check before it passed. It must be rerun after the fault is cleared, with a fresh
health receipt.

## Open questions

1. If the cone check ever fails on XPU, the receipts name the chunk and the differing byte count; the owner
   decides between `full` and investigating SDPA row independence.
2. The six four-card snapshots per chunk (≈ 0.3–0.5 s): is a cheaper but equally strong residence check
   acceptable to the owner? This is the largest remaining fixed cost.
3. Audio is still unconditioned per chunk and ≈ 0.03 s shorter than the video (as 113–116b).
4. 121 frames with the decoder graph may run short on xpu:3 (§ lever 3); dg0 at 121 is the fallback launch.
