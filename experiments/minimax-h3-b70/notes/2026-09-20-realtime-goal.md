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
| 2026-09-20 | duet steady state, 4 clips (`duet-20260920T054351Z`) | 4 clips 960x544 50 NFE in 1717 s = **429 s/clip (1.87x, 0.289 fps)**; all four sample phases finished inside a 1425-1446 s window (vs 2723 s serial, 1.88x sustained pipelining); clip-00 bytewise gate PASS. Import race in diffusers' lazy loader found and fixed (per-thread pipeline builds behind a lock) | **works, exact**; throughput holds with batch depth |
| 2026-09-20 | compute-balanced duet split (`SPLIT_INDEX=25`, `duet-20260920T061643Z`) | split was 24/26 by BYTES but every block has equal FLOPs; 25/25 + heads on rank1 rebalanced: 2 clips in 853 s wall = **426.5 s/clip (1.88x, 0.290 fps)**, sample.0 692.6 s vs 720.7 before (-3.9%), bytewise gate PASS (all four MATCH). Split is a pure device-assignment change, provably bit-exact | **works, exact**; new default recommendation |
| 2026-09-20 | faster SDPA kernel (flash/mem-efficient) | probed this torch/XPU build directly: `FLASH_ATTENTION` and `EFFICIENT_ATTENTION` both FAIL on bf16 ("unsupported ScalarType BFloat16"); the model runs the math path | **dead**; no faster exact attention kernel exists on this build |
| 2026-09-20 | overlap decode with sampling | memory analysis before building: two-proc decode needs 9.7 GiB VAE replica per card + 9.7 GiB blend copy on card0; sampling pins 24.4/22.9 GiB; every variant exceeds the 31.9 GiB card (card1 best case 22.9+9.7=32.6) | **dead by VRAM**; the ~55 s/clip serialized decode stays on the critical path |
| 2026-09-20 | 8-clip soak, shipped defaults (`duet-20260920T064019Z`) | 8 clips 960x544 50 NFE in 3281 s = **410 s/clip (1.95x, 0.302 fps)**; sampling pipelined 1.96x sustained (8 phases in a 2727-2776 s window vs 5446 s serial); gate PASS, zero faults, watchdog clean over 54 min | **works, exact**; throughput still improving with depth (2->4->8 clips: 426->429->410); floor is ~401 s/clip (346 sampling + 55 serialized decode) |
| 2026-09-20 | turbo LoRA 8-step, MEASURED on duet stack (`duet-20260920T074116Z`, 960x544, 9 NFE) | 2 clips in 273 s wall = **136.5 s/clip (5.9x vs baseline, 3.0x vs exact stack), 0.91 fps**; sampling 55-59 s/clip card-time (vs 346 at 50 NFE). Quality vs baseline clip-00: MAE 28.8/255, PSNR 14.4 dB = a DIFFERENT sample, not an approximation; visual A/B (turbo-vs-base-contact-sheet.jpg in run dir): both coherent, on-prompt (umbrella figure, neon rain), turbo darker/moodier — a human quality call, not a metric one | works, OFF lossless track by definition; with fp16 decode stacked it projects to ~92 s/clip (1.35 fps). USER DECISION DATA READY |
| 2026-09-20 | audio decode overlap (`h3_audio_proc.py`, persistent worker on the other card, default ON in two-proc mode; `AUDIO_OVERLAP=0` opts out) | the ~3 s/clip audio phase hides inside the 40 s video decode: `decode.audio.i` now measures **0.00 s/clip**; `duet-20260920T081242Z` gate PASS, all four hashes MATCH (audio decoded on card 1 is bytewise the audio from card 0). Two bugs found by the gate run: worker glob matched its own `-out.ready` answers, and ZE_AFFINITY_MASK renumbers the masked card to xpu:0 | **works, exact**; last serialized phase removed — batch decode tail is now pure video decode + write |
| 2026-09-21 | persistent VAE decode server (`h3_vae_duet.py --serve`) + audio overlap, combined | decode.video measured 55.7 s/clip vs 39.9 standalone — the delta is per-clip process spawn + 2x9.7 GiB replica reload; serve mode keeps workers resident across the batch (jobs over /dev/shm, same positional-tile protocol, plan asserted identical per job). **IMPLEMENTED, GATE PENDING**: blocked on an uncleared devcoredump on card2 from the freeze | code committed-ready; expect ~40 s/clip decode tail |
| 2026-09-20/21 | **incident: two host freezes** | standalone `h3_vae_duet.py` launched WITHOUT the smoke wrapper (no mem-watchdog): three procs loading the 9.7 GiB fp32 VAE in lockstep on a 15 GiB host spiked MemAvailable under 1.7 GiB; with no watchdog the first occurrence froze the desktop (repeat on 09-21 was watchdog-killed cleanly at tile 18, machine stayed up). Card2 latched a devcoredump; clearing is a root op | **rule, now absolute: GPU work only via `./scripts/smoke_h3.sh`** (systemd scope MemorySwapMax=0 + mem-watchdog 2048 MiB floor) |
| 2026-10-03 | **persistent VAE decode server, gate run** (`scripts/gate-session-20261003.sh`) | base model, 50 NFE, 960x544: clip-00 MATCHES `repeat-20260920T023257Z-a` on all four hashes with the server decoding in 40.8 s (`duet-20261003T224727Z`). That run then died on clip 1: both workers unlinked the shared `j<i>-z.st`, rank 0 crashed on `FileNotFoundError`, and the driver waited its full 900 s. Fixed (the server removes the file after both ranks report done; the audio worker is now stopped on failure too). Rerun on the final code, 2 clips with the turbo LoRA: 4/4 MATCH vs the fp32 turbo reference `duet-20260920T074116Z` (`duet-20261003T233113Z`); decode.video 52.4 s on the first clip (spawn + VAE load) and **41.1 s on every later clip, vs 55.7 s per clip before** | **works, exact**; the decode tail is now ~41 s/clip in a batch |
| 2026-10-03 | fp16 decode on the two-process path | the tile workers had been ignoring `--autocast`: a `VAE_AUTOCAST=fp16` two-proc run decoded in fp32 (same hash as fp32, same 41 s) while its receipt said fp16. With the setting actually applied: **decode.video 9.0 s/clip (20.1 s first clip) vs 41.1 s, 4.6x**; latents and audio hashes untouched. **But two identical runs gave different picture hashes on both clips** (`duet-20261003T233530Z` vs `duet-20261003T233845Z`) | fast and **not repeatable**: opt-in only, warned at preflight; cause not localized (single-card fp16 on xpu:1 is repeatable, so suspect card 0 or the per-process state) |
| 2026-10-03 | fp16 decode, single card, repeat re-check | decode-only of `repeat-20260920T023257Z-a` latents twice: 15.3 s each, bytewise-equal to each other, different from fp32 (as expected) | works, repeatable, lossy. Made the single-card default for a few hours on 2026-10-03, then **withdrawn the same night: the owner's direction is lossless only**, so fp32 is the default everywhere and fp16 is opt-in by name |
| 2026-10-03 | **clip files made byte-repeatable** | two clips with bit-identical picture tensors used to give different `clip.mp4` files. Cause found on the CPU by encoding one clip's frames repeatedly: x264's macroblock-tree rate control gives a different stream on every run of this build, even on one thread, and the mp4 muxer stamps a creation time. Fix in `write_mp4`: `x264-params mbtree=0` and `fflags=+bitexact` (about 5 % larger file at the same crf, same encode time). Each receipt now records `clip_mp4_sha256`. Gate: three exact duet runs (`duet-20261004T034605Z`, `...035024Z`, `...035545Z`), all 4/4 MATCH vs the fp32 turbo reference, and the same clip digest for clip-00 and for clip-01 in all three | **works, exact, deterministic end to end**: same seed and prompt now give the same file, not only the same tensors |
| 2026-10-03 | decode server robustness | (1) `_await_file` now fails within 0.25 s when a tile worker has died, instead of the caller's 900 s timeout; (2) the batch decoder and the duet remove their `/dev/shm` work folders on every exit and keep the logs under `<run>/decode-logs/` (a failed run had left 1.1 GiB of host RAM behind); (3) the audio worker is stopped on failure too. Covered by the same three gate runs | **works, exact**; stability only, no speed change |
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
