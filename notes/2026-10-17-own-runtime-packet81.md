# Packet81 routed-expert throughput round 3

CPU preparation is complete. [Analysis](../experiments/own-xpu-runtime/stage2/packet81-experts3/ANALYSIS.md)
was committed and pushed first as e2e3bed9c. The two expert kernels still
spend substantial work unpacking values and issuing loads. IQ2 already reads
eight grid values together, and IQ4 already has its small table in registers.
A new way to read the same activation bits cuts offline load instructions
from 51 to 27 for gate/up and from 79 to 31 for down, with no spills.
This does not establish a speed gain.

Four choices share one binary: production, gate-only, down-only and combined.
All pass two fresh runs with GNU and Intel. Each run checks 18 expert cases,
110,592 raw FP32 chains and 3,456 reduction trees. All eight full-size startup
checks pass and capture the intended selected kernels. Memory totals and
limits are unchanged. Both builds, 85 Python checks, four seals, five lane-A
plans, nine possible lane-B plans and both temporary queue plans pass.

Next is the coordinator's lane-A grid. Lane B admits only the exact A winner
that beats both production controls. [Commands and proposed jobs](../experiments/own-xpu-runtime/stage2/packet81-experts3/WINDOW.md),
[CPU closeout and evidence](../experiments/own-xpu-runtime/stage2/packet81-experts3/CPU-PREPARATION-CLOSEOUT.md).
No GPU, model, service, live queue or host setting was changed. Existing
packet, screen and ops trees were left untouched apart from the two new
proposed files. The build is about 169 MB and peak compiler RSS was 710 MiB.

The requested pull --rebase refused unrelated live orchestration edits.
Fetch confirmed main already matched origin/main, so those edits were
preserved. Another packet's concurrent commits were preserved as well.

## Device result and closeout (coordinator, 2026-10-17 23:15–23:38 UTC, lane A)

All exact. Production mean 54.314 tok/s (54.343 / 54.285):

| View | tok/s | vs production |
|---|---:|---:|
| `gate-input-packed` | 54.349 | +0.07% |
| `down-input-packed` | 54.379 | +0.13% |
| `input-packed` | 54.256 | −0.10% |

**Closed as neutral.** Cutting static loads (51→27, 79→31) did not move the expert class, so the experts' limiter is not load issue. It is likely IQ2_S grid-lookup/dequant ALU or latency. The lane-B confirmation was dropped. DO-NOT-REPEAT further load-count reductions on the expert kernels without an ALU/latency analysis that predicts a gain.
