# Qwen3.8 Flash-Next HC combine-norm exact confirmation A1: pass (2026-09-02)

Date: 2026-09-02 10:10--10:17 EDT, boot `67848b88-c7c7-452a-bef1-124364a300b9`
(BIOS 2.4a, root SSD Gen4 x4 under the validated clearance)
Status: lossless component positive; candidate advances to integration
planning, not yet an endpoint result

## Result

`tools/run-q38-hc-combine-norm-exact-confirmation-a1.sh` (runner
`73a6fa85...`, gate `102df2a5...`, unchanged candidate core and summarizer)
ran the frozen real-weight bracket: four sentinels, 12 matched fresh-process
control/candidate/control cells, the 95-call graph cycle, 100 changing-input
exact checks for both outputs, and the adversarial BF16 cases, on one B70
with the external checkpoint.

| gate | value |
|---|---|
| all 12 cells exact (both outputs, eager and captured) | true |
| positive cells | 12 / 12 |
| median matched reduction | `21.747555%` |
| worst cell reduction | `21.689318%` |
| median saved per 95-call cycle | `641.09 us` |
| material (>=5% or >=1 ms) | true |
| control drift within 2% | true |
| corrected-event delta / root port | 0 / 0 |

The candidate hoists only the immutable `1 + norm_weight.float()` construction
and keeps Torch sigmoid/rsqrt/order and the explicit BF16 combine
round/reload boundary, which is why it survives the XPU exactness gate that
the gate-mix staging candidate failed minutes earlier.

Evidence:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-hc-combine-norm-exact-confirmation-a1/`
(`summary.json`, `final-health.txt`, `identity.txt`, 36 arm JSONL files,
SHA256SUMS). Two admission-blocked attempts without GPU work are preserved
beside it; see the prereg amendments for the counter-parsing and
ancestor-exclusion fixes.

## Whole-step expectation

About `0.64 ms` per target token against A55's roughly `52 ms/token`, on the
order of 1.2%. Real but small; it should ride along with the tuned M1 map in
a later combined arm rather than pay for its own model load. Integration
requires a default-off selector in the live HC path and the same exact
eager/captured qualification before any endpoint arm.
