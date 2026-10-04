# Packet 93b: lean conditioning is exact and saves about 0.36 GPU-s per clip; the short window ran but its probe bound was wrong (2026-10-04)

Server `encoder-server-window-93b` (packet `prepared-encoder-window-93b`,
manifest `655eac57...`), kernel 7.0.0-38, admitted on this boot with health
receipt `data/health/four-card-health-20261004T0413Z.json`, launched 04:13 UTC,
stopped cleanly 04:29 UTC, no fault line, no lockup. Runner
`scripts/run-campaign-93b.sh`; receipts in `data/window-93b/`.

| Arm (replica decode placement) | Clips exact | Compute-engine seconds per clip: xpu:0 / xpu:1 / xpu:2 / xpu:3 | Total |
| --- | ---: | --- | ---: |
| control | 36/36 | 1.431 / 1.431 / 1.159 / 1.423 | 5.44 |
| lean conditioning | 36/36 | 1.280 / 1.330 / 1.134 / 1.339 | 5.08 |

- **Lean conditioning is exact.** Both arms match the existing references
  byte for byte, and the context sentry shows the bytes fed to the first
  transformer forward of each stage are identical in the two arms for all ten
  fixtures. It removes about 0.36 GPU-s per clip (6.6 %), more than the
  survey's estimate. It becomes the default for speed arms.
- The stream interval did not move in 36 clips (mean 1.645 s control, 1.663 s
  lean); these arms are too short for a speed verdict.
- **Short-window encoder on the real graph path:** all 384 per-bucket graphs
  captured, results identical across both encode workers and repeats, 0.343 s
  per encode at 64 tokens against 1.70 s at 1024, memory within limits. The
  probe then refused it as `window-not-close`: maximum difference 0.125 on
  values up to about 45. That is one bf16 rounding step on a few elements
  (mean difference about 1.1e-4): the conditioning tensor is rounded to bf16
  inside the encoder, and the 1e-3 max/max bound written into the probe
  cannot be met by any bf16-rounded tensor. The bound was the agent's
  mistake, not a defect in the window. So the reference passes, the
  finished-clip comparison and the windowed arm did not run. Packet 93c
  corrects the bound (mean relative difference, at most two bf16 steps,
  at most 5 % of elements differing) and reruns them.
