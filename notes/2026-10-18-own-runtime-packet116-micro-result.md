# Packet 116 QSA attention + selection schedule: micro below gate, closed (2026-10-18)

Lane B, card 2, `packet116-micro-B-1` 11:17–11:18 UTC, complete current-mode QSA layer, 40 measured iterations per mode per context, all state comparisons exact. Second process pulled (result unambiguous). No fault (count 2).

| Context | Production qsa.attention + qsa.select µs | p116 µs | Ratio |
| ---: | ---: | ---: | ---: |
| 128 | 68.33 | 63.96 | **0.936** |
| 4096 | 587.6 | 554.7 | **0.944** |

Kill gate ≤ 0.6× at context 128. The exact re-partition (more work-groups under the identical split-32 reduction tree) removes only ~6% of the latency; the remaining cost is not work-group count. Closed.

Evidence: `experiments/own-xpu-runtime/stage2/packet116-qsa-schedule/micro/evidence/micro-B-1/`.
