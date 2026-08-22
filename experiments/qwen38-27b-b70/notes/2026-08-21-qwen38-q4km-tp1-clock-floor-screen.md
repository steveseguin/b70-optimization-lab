# Qwen3.8 Q4_K_M TP1: GPU0 clock-floor screen

Date: 2026-08-21

Status: **bounded negative: the frequency floor is a dead lever on this
workload; the card is sustained-power-capped.** User-authorized clock
mutation ("you can touch clocks if that helps get better results"),
performed and fully restored.

## What ran

- Writer inventory: no competing GPU clock writers (no `xe-b70-minfreq`
  unit locally; `auto-cpufreq` not-found/dead; `hwclock` is the RTC).
- Pre-state captured: GPU0 range 400-2800 MHz (stock).
- Set `xpu-smi config -d 0 -t 0 --frequencyrange 2800,2800` (readback
  confirmed min=max=2800), launched the current lane server, and probed.
- Restored 400-2800 afterward with readback proof; no other card touched.

## Findings

1. **Pinned at 2800, the card still runs 2633-2650 MHz under decode at a
   steady ~230 W.** The observed "droop" (2633-2683 MHz across today's
   samples) is not a DVFS governor choice a floor can override — it is
   sustained-power throttling.
2. `hwmon` for GPU0 (`xe`): `power1_cap = 230 W` (matching the measured
   draw exactly), `power1_crit = 460 W`. The card operates pinned to its
   sustained cap during single-stream decode.
3. Rates confirm neutrality: fixed-seed probe `27.991 tok/s` pinned vs
   `28.00` stock; long 800-token probe `27.891` pinned vs the same fused
   class stock. Probe text byte-identical to the oracle (clock state does
   not touch arithmetic).

## Interpretation and disposition

Raising `power1_cap` is the only lever behind this wall, and it is a poor
one here: decode is memory-bandwidth-bound (MMVQ at the streaming ceiling),
so recovering the last ~6% of core clock is worth an estimated +1-2%
end-to-end at best — and 230 W is plausibly the vendor board rating for
this cooler, making a raise a hardware-safety decision for the operator,
not an agent-side optimization. No power-cap change was made. The lane's
recorded identity remains the stock 400-2800 range. Redirecting effort to
the larger in-graph MMVQ tax pool (~2-3 ms/token).
