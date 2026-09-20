# MiniMax-H3 two-B70: lossless speed work, 2026-09-20 — publication draft

**Headline:** 1.82x throughput on lossless, deterministic 960x544 (the trained canvas) video
generation on two Intel Arc Pro B70s — 800.8 s to 440.5 s per 5.17 s clip (124 frames + 32 kHz
stereo audio), with every output bit-identical to the reference path. Effective generation rate
0.155 -> 0.282 fps. Goal track: 24 fps realtime.

## What changed (all exact, all gated bytewise)

1. **Batch mode** (`--prompts-file`): encoder, denoiser and VAEs load once per batch.
   ~49 s saved per clip after the first. Gate: batch clip hashes == standalone receipts (all four
   hashes: video tensor, audio tensor, both latent sets).
2. **Duet sampling** (`h3_duet.py`): the block-24 model split becomes two PROCESSES, one card
   each, with the per-forward crossing over /dev/shm; two clips stagger through the pipeline so
   neither card idles. 1.87x on the sampling phase. The threaded version of this pattern measured
   1.01x (the GIL serializes this torch/XPU build's blocking ops) — processes were the fix.
3. **Two-process VAE decode** (`h3_vae_duet.py`, `--vae-decode two-proc`): same pattern applied
   to the 105-tile video decode. 39.9 s vs 79.96 s per clip at 960x544 fp32 (2.0x).

## Gates

- Baseline: `repeat-20260920T023257Z-a/b` — 960x544, 50 NFE base schedule, fp32 decode,
  REPEAT GATE bytewise-equal, 800.8 s/clip.
- Combined run: `duet-20260920T052148Z` — clip-00 matches the baseline receipt bytewise (all
  four hashes). Small-canvas gates: `batch-20260920T051559Z`, `duet-20260920T042216Z` vs
  `repeat-20260920T021446Z-a`.
- Determinism: no `--deterministic` flag needed; repeats matched bytewise without it.

## Not in this packet (parked, user-gated, measured)

- fp16 VAE decode: 5.0-5.2x on decode, ~0.03 of an 8-bit level mean pixel delta — NOT lossless.
- 8-step turbo LoRA: 6.25x fewer NFE — a distilled adapter, changes the output distribution;
  off the lossless track by definition.

## The remaining gap

24 fps at 960x544 lossless needs 124 frames per 5.17 s of wall = 41.7 ms/frame; sampling alone
is 50 NFE x ~1.28 PFLOP. On two B70s (~94 TFLOP/s per card sustained) the exact arithmetic floor
for sampling is ~340 s/clip with perfect overlap — 66x short of realtime. Further exact levers
are small (load overlap ~15 s, deeper batching amortization). Closing the gap to 24 fps requires
a schedule/distillation decision (quality) or new hardware — tracked in
notes/2026-09-20-realtime-goal.md.

## Reproduce

```
cd experiments/minimax-h3-b70
LORA= HEIGHT=544 WIDTH=960 VAE_DECODE=two-proc \
  PROMPTS_FILE=<two-or-more-prompts.txt> BATCH_REF_0=repeat-20260920T023257Z-a \
  ./scripts/smoke_h3.sh duet
```
