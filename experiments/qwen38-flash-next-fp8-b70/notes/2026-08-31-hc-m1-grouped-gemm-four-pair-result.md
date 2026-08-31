# Qwen3.8 Flash-Next FP8 HC M1 grouped-GEMM four-pair result

Date: 2026-08-31
Status: exact component positive for layer-0/up; other pairs not eligible

All four real-weight control/candidate/control pairs completed with exact
production-consumed outputs, one hash per arm across 100 repeats, and zero in
every discarded output across every repeat. The host remained healthy and no
server, full model load, reboot, or protected-result change occurred.

| Layer | Projection | Control median | Grouped median | Reduction | Control drift | Follow-up |
|---:|:---|---:|---:|---:|---:|:---|
| 0 | down | 39.3185 us | 39.5522 us | -0.59% | 0.05% | no |
| 0 | up | 35.1959 us | 12.2767 us | 65.12% | 2.21% | yes |
| 47 | down | 40.5114 us | 39.5169 us | 2.45% | 0.24% | no |
| 47 | up | 41.3088 us | 10.5981 us | 74.34% | 23.72% | no: control drift |

The down family is closed as neutral under the frozen 5% gate. Layer-0/up is a
large lossless component positive. Layer-47/up shows the same large directional
effect, but its first control was noisy and the bracket correctly withheld
eligibility. Two fresh matched up-only brackets per sampled layer are the next
bounded discriminator.

This remains a hot-weight component result. It does not measure 48-layer
round-robin behavior, kernel integration, target decode, or endpoint quality,
and authorizes no performance claim outside this screen. Exact values and raw
result checksums are in the
[structured result](../data/20260831-hc-m1-grouped-gemm-four-pair-screen.json).
