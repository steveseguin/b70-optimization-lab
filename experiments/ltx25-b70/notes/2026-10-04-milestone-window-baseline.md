# Milestone: the short-window text encoder becomes the baseline (owner's decision, 2026-10-04)

**What changed.** Prompts are no longer padded to 1024 tokens before the text
encoder runs. The encoder processes only the last W tokens, W being the
smallest of 64, 128, 256, 512 that holds the prompt's real tokens (1024 for
longer prompts), with the positions those tokens would have had in the padded
layout. The padding was masked and its results were discarded, so nothing the
model uses is skipped.

**What did not change.** The model, its weights, the precision of every
stage, the number of sampling steps, the seeds, the resolution, the frame
count. Nothing is cached or reused between clips.

**Why the output is not byte-identical to before.** The GPU's matrix
multiply adds in a different order when it is given fewer rows, which changes
last digits in the encoder output (4-6 parts per million, the same as running
the unchanged encoder on a CPU instead of the GPU). The sampler runs in bf16
and re-rolls its own rounding on any change of input, so the finished clip is
a different take of the same scene: PSNR 17-27 dB against the earlier clip of
the same prompt and seed, the way two seeds differ. Evidence:
[probe](2026-10-04-encoder-suffix-window-probe.md),
[packet 93c results and side-by-side frames](2026-10-04-packet-93c-results.md).

**The owner's decision, in his words (2026-10-04):** "we can just note this
milestone change, and go forth with testing and samples with the current
results as the baseline for the new reference data ... If its just a random
seed change, but everything else is mathematically the same, so same quality,
we can just go forward from here."

**Rules from here on.**

- Reference clips: `stability-01-w93c-<fixture>` (output/validation), fixtures
  file `data/stability-01-window-prereg.json`. Every later change is gated
  byte for byte against these.
- The padded-encoder references (`baseline-01`, `speed-oracle-*`,
  `stability-01-r01-*`) are kept as history and are not mixed with the new
  ones. Numbers before this milestone were verified against them.
- This is recorded as an output-changing change, accepted by the owner. It is
  not evidence that other output-changing changes are acceptable; each one
  goes to the owner.
- Equal quality rests on the argument above and on the side-by-side frames.
  A scored comparison over a larger prompt set has not been run.

**Baseline numbers (packet 93c, window + lean conditioning, 116 clips, all
byte-identical to the new references):** 1.39 s per clip mean (18.0 fps
equivalent), 3.82 GPU-seconds of compute per clip: xpu:0 1.24, xpu:1 1.33,
xpu:2 0.40, xpu:3 0.85. Perfectly balanced over four cards that is 0.96 s per
clip. The sampler cards are saturated and xpu:2 is mostly idle, so the next
lever is spreading the transformer blocks over all four cards.
