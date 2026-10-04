# Packet 93c: the short-window encoder is fast and repeatable, but the finished clip is a different take, not the same clip (2026-10-04)

Server `encoder-server-window-93c` (packet `prepared-encoder-window-93c`,
manifest `b02b844e...`), kernel 7.0.0-38, health receipt
`data/health/four-card-health-20261004T0413Z.json`, 04:33-04:57 UTC, clean
stop, no fault, no lockup. Runner `scripts/run-campaign-93c.sh`; receipts in
`data/window-93c/`.

## Results

| Arm | Clips verified | Exact | Interval median / mean | Compute-engine s per clip: xpu:0 / 1 / 2 / 3 | Total |
| --- | ---: | ---: | ---: | --- | ---: |
| control (padded encoder) | 36 | 36 vs existing references | 1.82 / 1.59 s | 1.36 / 1.37 / 1.13 / 1.31 | 5.17 |
| lean conditioning | 36 | 36 vs existing references | 2.16 / 1.68 s | 1.30 / 1.37 / 1.14 / 1.37 | 5.18 |
| window reference pass 1 | 10 | pass 1 = pass 2, byte for byte | 1.30 / 1.35 s | 1.11 / 0.84 / 0.30 / 1.12 | 3.37 |
| window reference pass 2 | 10 | (same) | 1.34 / 1.39 s | 1.40 / 1.05 / 0.32 / 1.36 | 4.12 |
| window + lean, 120 prompts | 116 | 116 vs the NEW references | 1.52 / **1.39 s** | 1.24 / 1.33 / 0.40 / 0.85 | **3.82** |

- The window qualified: identical bytes on both encode workers and on
  repeats, capture proof per bucket, conditioning within the bf16-aware
  bounds. Encode job median 0.56 s against 3.18 s.
- The two reference passes are byte-identical to each other, and 116 further
  clips are byte-identical to them. The windowed pipeline is deterministic.
- Stream mean 1.39 s per clip (18.0 fps equivalent) against 1.59-1.68 s for
  the padded arms in the same run. The sampler cards (xpu:0, xpu:1) are now
  the busy ones; xpu:2 is at 0.40 s per clip.
- The lean arm's saving seen in 93b (0.36 GPU-s) did not show here (5.17 vs
  5.18): 36-clip arms are too short to size it. It is exact either way.

## The finished-clip comparison (the owner's first condition)

Windowed reference clips against the certified padded-encoder clips of the
same fixture and seed (`window-oracle-vs-1024-oracle.json`):

| Fixture | PSNR | Mean pixel difference (0-255) | Pixels off by more than 1/255 |
| --- | ---: | ---: | ---: |
| boat | 19.4 dB | 17.8 | 99.97 % |
| marble | 22.4 dB | 12.6 | 99.5 % |
| bird | 16.8 dB | 24.3 | 99.8 % |
| pendulum | 18.2 dB | 17.8 | 98.1 % |
| rain | 24.8 dB | 8.5 | 96.9 % |
| paper | 20.3 dB | 12.9 | 99.0 % |
| candle | 21.1 dB | 15.7 | 99.9 % |
| pour | 18.7 dB | 18.5 | 99.1 % |
| fabric | 18.0 dB | 20.3 | 99.8 % |
| wheel | 27.1 dB | 2.7 | 43.8 % |

**The difference is not negligible.** These are different clips: the same
scene, subject and look, with a different composition and motion, the way two
seeds differ. Side-by-side frames are in
`data/window-93c/finished-clip-comparison/` (padded encoder left or above,
short window right or below); by eye the quality is the same and the content
is a different take.

Why a rounding-level change in the conditioning (a few elements one bf16 step
apart) becomes a different clip: the sampler runs in bf16, each of its
roughly 500 block evaluations rounds to 8 bits of mantissa, and any change in
the input re-rolls all of that rounding. The expectation written before the
run ("the same video with last-digit differences") was wrong.

Not shown: that the unchanged pipeline on different hardware (for example
the padded encoder run on the CPU, which differs from the GPU by the same
4-6 ppm) also yields a different take. That is the expected result and would
make the point that byte-identity here is tied to one machine's rounding,
but it has not been run.

## Status

The owner's first condition ("negligible finished-clip difference") is not
met as stated. The windowed encoder is not adopted. The new references
(`stability-01-w93c-*`, `data/stability-01-window-prereg.json`) exist and are
internally consistent, and stay unused until the owner decides whether a
different take of equal quality is acceptable.
