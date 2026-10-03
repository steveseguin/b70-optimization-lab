# Kernel soak, two-B70 host: faults per two-card FP8 service start (2026-10-03)

Runner: `scripts/fp8-start-cycle-soak.sh` (one health probe, then N cycles of start, 12-prompt strict
parity against the comm-2 no-MTP reference, stop; fault lines counted per phase; halt at the first one).
Raw outputs: `/mnt/fast-ai/bench-results/kernel-soak-20261003/<label>/`. Each label's `identity.json`
records the kernel, GuC, compute-runtime, swappiness, boot id and git revision.

| Label | Kernel | Cycles clean | Fault lines | Exact | tok/s median (min to max) | Ready, median | Lowest MemAvailable |
|---|---|---:|---:|---|---|---:|---:|
| `k31` | 7.0.0-31-generic | 10 / 10 | 0 | 12/12 every cycle | 90.21 (89.85 to 90.41) | 151 s | 2,877 MiB |

## What the baseline says

Ten starts in a row on the *old* kernel were clean. Every September start fault predates, or
immediately preceded, the no-swap launcher change of 2026-09-19 (`--memory-swap 12g`), and the starts
measured since then (three validation starts on 2026-09-19 and today's ten) are all clean on 7.0.0-31. So the
start faults were most likely the container swapping its staging pages during the weight load, which
is fixed, and a kernel change cannot show an improvement on this particular measure: the best it can
do is also score ten out of ten.

What this soak does not cover: a service start that follows MiniMax or one-card work on the same boot
(three of the five September faults), and fault lines caused by killing a busy job. Those are the
conditions under which a newer kernel could still differ.
