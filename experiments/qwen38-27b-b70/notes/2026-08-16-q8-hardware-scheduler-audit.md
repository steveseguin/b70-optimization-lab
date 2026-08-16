# Qwen3.8 Q8 TP2 hardware scheduler audit

Date: 2026-08-16  
Disposition: closed; no persistent setting changed

## Why this was tested

Before changing another kernel, this audit checked whether the remaining TP2
gap was partly an avoidable B70 scheduler, clock, or power-limit constraint.
The experiment used the accepted target-only Q8 binary and model after a clean
reboot.

## Result

Both cards were already configured for their reported maximum GPU clock of
`2800 MHz`, a `275 W` burst limit, and the default `timeslice` scheduler. The
Level Zero management API rejected the reversible exclusive-scheduler request
with `ZE_RESULT_ERROR_UNSUPPORTED_FEATURE`. The command stopped before changing
either card; a subsequent readback confirmed that both remained in the original
timeslice mode (`1000 us` interval, `640000 us` yield timeout).

The installed management CLI also would not accept a scheduler interval below
`5000 us`, even though the active default readback was `1000 us`. The timeslice
interval was therefore not changed: an exact same-boot restoration could not be
guaranteed without a reboot.

Two correct TP2 controls used `-dev SYCL0/SYCL1` and produced these five-sample
decode means:

| Run | Mean decode | Standard deviation |
| --- | ---: | ---: |
| Control 1 | `34.418472 tok/s` | `0.116719` |
| Control 2 | `34.450882 tok/s` | `0.166118` |

The pooled ten-sample mean was `34.434680 tok/s`. These `p0/n128` llama-bench
controls are diagnostic only; they do not replace the accepted fixed-prompt
endpoint result.

A separate decode A/B/B/A arm tested whether holding both cards close to their
maximum clock avoided ramp latency. The treatment set each valid GPU clock range
to `2750`–`2800 MHz`; the controls used the normal `400`–`2800 MHz` range. Each
arm ran three `p0/n256` samples with the accepted Q8 TP2 binary:

| Arm | Clock range | Mean decode |
| --- | --- | ---: |
| A1 | `400`–`2800 MHz` | `36.031442 tok/s` |
| B1 | `2750`–`2800 MHz` | `36.043457 tok/s` |
| B2 | `2750`–`2800 MHz` | `36.440978 tok/s` |
| A2 | `400`–`2800 MHz` | `36.807614 tok/s` |

The pooled treatment mean was `36.242218 tok/s` versus `36.419528 tok/s` for
the pooled controls (`-0.487%`). Both cards were restored to `400`–`2800 MHz`
immediately after B2 and the restoration was verified by readback. This arm is
noise-bounded but clearly supplies no useful gain.

During the second control, 200 telemetry samples per GPU observed maximum
graphics clocks of `2800 MHz` on both cards, no throttle reason, and peak sampled
power of `189.79 W` and `201.89 W`. The installed xpu-smi stack returned `N/A`
for memory-bandwidth and compute utilization, so those columns must not be
inferred from power alone.

One invalid preliminary command used `-dev SYCL0,SYCL1`. llama-bench interpreted
the comma as separate device cases and emitted two one-card rows around 18 tok/s;
those rows are excluded. Tensor-parallel llama.cpp device syntax uses a slash.

## Decision

Do not retry exclusive scheduling or minimum-clock pinning on this
driver/runtime combination. Do not claim that a power override was tested: no
power value was changed, and the cards already reached their configured clock
ceiling without throttling. The remaining work is in the Q8/collective
execution path, not an exposed hardware control.

Structured evidence is in
[`data/2026-08-16-q8-hardware-scheduler-audit.json`](../data/2026-08-16-q8-hardware-scheduler-audit.json).
Raw logs remain locally under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-scheduler` and
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-minclock-abba`;
hashes are recorded in the structured evidence.
