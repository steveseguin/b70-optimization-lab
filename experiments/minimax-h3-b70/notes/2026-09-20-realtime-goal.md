# MiniMax-H3 realtime goal: ledger and idea list (opened 2026-09-20)

**Goal (user, 2026-09-19/20):** iterate MiniMax-H3 on the two-B70 host toward **24 fps realtime
generation at >= 960x544, deterministic and lossless** ("without cheating"). Publish only after
confirmed significant improvements. Keep a record of what works and what does not, and a standing
list of ideas.

**Definition of lossless for this goal:** bit-identical output to the base model's reference
schedule (51 scheduler points = 50 NFE, rectified-flow Euler, no guidance, fp32 VAE decode,
`VAE_AUTOCAST=off`) at fixed seed. Any change that alters one bit of video/audio/latents is
*not* on the goal track, however small (fp16 decode, turbo LoRA, FP8 anything, two-card decode
without the bytewise gate).

**Quality reference vs speed tracks.** The turbo 8-step LoRA and fp16 decode are *measured,
parked, user-gated* options (README, batch window 4). They are not counted toward this goal
unless the user rules otherwise.

## The gap

| config | wall / 5.17 s clip | effective fps | gap to 24 fps |
|---|---:|---:|---:|
| 960x544, 8 NFE turbo, fp32 decode (measured 2026-09-19) | 243.8 s | 0.51 | 47x |
| 960x544, 50 NFE base, fp32 decode (this ledger's baseline) | 800.8 s | 0.155 | 155x |

Target: 124 frames per 5.17 s of wall (960x544) = every pipeline phase combined must fit the
frame budget of 41.7 ms/frame.

## Baseline


Baseline detail (repeat-20260920T023257Z-a/b, REPEAT GATE bytewise-equal, all four hashes):
sample 680.6 s, decode.video ~80 s, loads ~49 s, encode/decode.audio/write ~6 s.
155.0 s of wall per second of video. Sampling is 85 % of the run at 50 NFE -- which makes
lever 5 (staggered pipeline) and raw kernel work far more important at the base schedule
than they were at 8 NFE, and the load/batch levers relatively smaller (6 % not 20 %).

## Ledger — what works, what doesn't

| date | lever | result | verdict |
|---|---|---|---|
| 2026-09-20 | batch mode (`--prompts-file`, lever 4) | 2 clips at 960x544 50 NFE in 1479.3 s vs 1601.6 standalone; clip-00 hashes MATCH standalone baseline repeat-20260920T023257Z-a bytewise (all four) | **works, exact**; ~49 s saved per additional clip (6 % at 50 NFE; 20 % at 8 NFE) |
| 2026-09-20 | **duet** (lever 5, process-per-card stagger, `h3_duet.py`) | 2 clips at 960x544 50 NFE: sample phases overlapped, 720+727 s concurrent vs 1361 s serial (1.87x on sampling); whole run 930 s = **465 s/clip vs 800.8 baseline (1.72x)**, 0.155 -> 0.267 fps. Both clips' hashes MATCH standalone receipts bytewise (clip-00 vs repeat-20260920T023257Z-a, all four). CPU-side scheduler math proved bit-identical to XPU. Runs: duet-20260920T042216Z (448x256 gate), duet-20260920T042549Z (960x544 gate) | **works, exact**; per-clip sample +6 % vs standalone (wire + transfer contention) but throughput 1.87x |
| 2026-09-20 | two-process VAE decode (`h3_vae_duet.py`, lever 2 fixed) | 960x544 decode+blend **39.9 s vs 79.96 s single-card (2.0x)**; video tensor sha256 MATCHES repeat-20260920T023257Z-a bytewise. Standalone decode-only tool so far; pipeline integration (run as the batch decode path) is the next step | **works, exact** |
| 2026-09-20 | **combined: duet + two-proc decode** (`VAE_DECODE=two-proc ./smoke_h3.sh duet`) | 2 clips 960x544 50 NFE in 881 s wall = **440.5 s/clip vs 800.8 baseline (1.82x), 0.282 fps**; clip-00 hashes MATCH baseline bytewise (all four). Run: duet-20260920T052148Z | **works, exact**; current best goal-track configuration |
| 2026-09-19 w4 | fp16 autocast decode | 5.0-5.2x on decode.video; not bit-identical (max 7.5/255 levels) | works, OFF goal track (lossy); user decision pending |
| 2026-09-19 w4 | two-card tiled decode (threads) | 1.01x — GIL serialised the two workers | **doesn't work as threads**; retry as process-per-card |
| 2026-09-19 w4 | share qkv rotation (int8) | proven exact on CPU; ~2-5 s of 153 s | works, small, int8-only |
| 2026-09-19 w4 | int8 denoiser overall | +40 % sample time (no fused int8 GEMM on XPU) | doesn't pay on this hardware; keep as fidelity control |
| (pre-flight) | cache dequantised BF16 weights | — | infeasible (speed-plan §2) |

## Idea list — ranked by expected gain / effort / risk

1. **Batch/resident mode** (speed-plan §3): one process, N prompts, each model loaded once.
   Saves 49.4 s/clip (~20-25 %). Bit-identical by construction (no arithmetic change; per-clip
   seeded generators). Host RAM: write+free each decoded clip before the next. ~120 lines.
   Gate: repeat gate per clip vs single-run receipts; `[mem]` VmHWM flat across clips.
2. **Two-card decode, process per card** (fixes measured lever 2): ~half of decode.video
   (80 s at 960x544 fp32). Bit-identical gated bytewise vs single-card decode of same latents.
   Needs IPC of tile slices through host RAM (127.0.0.1 socket or shared file; the tensors are
   small per tile). Determinism risk: none new — each tile decoded by the same code as single.
3. **Overlap loads with idle cards** (lever 3): card-1 denoiser shard loads during encode;
   VAE copy B during copy A's first tiles. ~12-15 s. Exact. ~40 lines.
4. **Staggered two-clip pipeline through the block-24 split** (lever 5): the sample phase's
   idle half (~109 card-s per clip) runs a second clip. Ideal ~54 s/clip amortised at 8 NFE —
   the only lever that touches sampling. Pruned-only (activation budget: 12.5 GiB free vs
   4.88 GiB/clip). High effort; synchronous `cross_card()` must be overlapped with compute.
   Exactness: clips never share arithmetic; repeat gate per clip.
5. **torch.compile / XPU graph capture on the denoiser forward**: risky for bit-identity
   (fusion changes reduction order). Test-only lever: if compiled output is not bit-identical
   to eager at fixed seed, dead for this goal. Medium effort, unknown gain.
6. **fp32->tf32/xetla GEMM paths in VAE decode**: VAE decode is fp32 GEMM-bound (speed-plan
   §1.2). An exact fp32 path cannot change dtype; but a *faster fp32 GEMM* (different tiling,
   same fp32 accumulation order?) — almost certainly NOT bit-identical. Likely dead for the
   goal track; listed for completeness.
7. **Reduced canvas scheduler tricks / step distillation**: all lossy by the goal's definition.
   Parked with turbo LoRA.
8. **CPU offload of audio branch during video decode**: audio decode is 2.93 s; not worth it.
9. **Kernel-level attention improvements in sample phase**: sample tracks FLOPs to 1.6 %
   (compute-bound, fused SDPA already); no headroom without changing arithmetic. Dead end
   unless hardware-level: check oneDNN/XPU SDPA backend versions for a faster *bit-identical*
   fused kernel — possible but unlikely.

## Rules

- Every candidate gets the repeat gate (two runs, same seed, four hashes) plus, where
  applicable, bytewise equality against the lossless reference of the *same latents*.
- Anything that changes a bit is recorded here as measured and parked for the user, never
  silently adopted.
- Publish only after a confirmed significant improvement (user reviews first).
