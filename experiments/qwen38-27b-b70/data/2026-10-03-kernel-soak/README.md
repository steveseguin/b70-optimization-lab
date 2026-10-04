# Kernel soak, two-B70 host: faults per two-card FP8 service start (2026-10-03)

Runner: `scripts/fp8-start-cycle-soak.sh` (one health probe, then N cycles of start, 12-prompt strict
parity against the comm-2 no-MTP reference, stop; fault lines counted per phase; halt at the first one).
Raw outputs: `/mnt/fast-ai/bench-results/kernel-soak-20261003/<label>/`. Each label's `identity.json`
records the kernel, GuC, compute-runtime, swappiness, boot id and git revision.

| Label | Kernel | Cycles clean | Fault lines | Exact | tok/s median (min to max) | Ready, median | Lowest MemAvailable |
|---|---|---:|---:|---|---|---:|---:|
| `k31` | 7.0.0-31-generic | 10 / 10 | 0 | 12/12 every cycle | 90.21 (89.85 to 90.41) | 151 s | 2,877 MiB |
| `k31-after-h3` | 7.0.0-31-generic, same boot, after 7 MiniMax duet runs and 2 decode-only runs | 3 / 3 | 0 | 12/12 every cycle | 90.22 (90.20 to 90.36) | 151 s | 3,236 MiB |
| `k38` | 7.0.0-38-generic, first GPU work after the reboot (ran by itself from `scripts/postboot-kernel-soak.sh`) | 10 / 10 | 0 | 12/12 every cycle | 90.27 (89.88 to 90.40) | 151 s | 2,989 MiB |

## What the baseline says

Ten starts in a row on the *old* kernel were clean. Every September start fault predates, or
immediately preceded, the no-swap launcher change of 2026-09-19 (`--memory-swap 12g`), and the starts
measured since then (three validation starts on 2026-09-19 and today's ten) are all clean on 7.0.0-31. So the
start faults were most likely the container swapping its staging pages during the weight load, which
is fixed, and a kernel change cannot show an improvement on this particular measure: the best it can
do is also score ten out of ten.

The `k31-after-h3` row is the pattern behind three of the five September faults: a two-card service
start that follows other GPU work on the same boot. Three starts after nine MiniMax runs were clean
too. What is still not covered: one-card FP8 research servers before the start, and fault lines caused
by killing a busy job (the 2026-09-21 kill left a copy-engine CAT error). Those are the conditions
under which a newer kernel could still differ.

Kernel 7.0.0-38 was installed after the 7.0.0-31 runs (7.0.0-31 stays installed as the fallback,
GuC 70.54.0 and compute-runtime unchanged).

## Verdict

**The two kernels are indistinguishable on this test: ten clean starts each, the same speed to within
a tenth of a token per second, the same start time.** 7.0.0-38 is therefore safe to stay on, and it is
the better place to be because it carries real `xe` fixes (teardown deadlock, page-table binds) that
this soak cannot exercise. It did not *cure* anything here, because after the no-swap launcher change
there was nothing left for this test to cure. The chat service is left running on 7.0.0-38 (unit
`fp8-soak-k38-c10`, state `/mnt/fast-ai/bench-results/kernel-soak-20261003/k38/c10/service`).
