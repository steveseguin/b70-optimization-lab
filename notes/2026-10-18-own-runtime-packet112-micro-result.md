# Packet 112 route selection: micro below kill gate, closed (2026-10-18)

Lane B, card 2, two fresh processes (`packet112-micro-B-1` 09:00–09:01 UTC, `-B-2` 09:03), 1,024 timed calls per view per process on real router inputs, 2,048 correctness cases (512 nonfinite) all exact. No fault (count 2).

| Process | Production route µs (median) | p112 µs | Ratio |
| --- | ---: | ---: | ---: |
| B-1 | 16.88 | 15.62 | **0.926** |
| B-2 | 16.98 | 15.62 | **0.920** |

Kill gate was ≤ 0.5×. Cutting work-group barriers from 27 to 14 (one subgroup per state row) saves only ~1.3 µs per call (~0.03 ms per half). Closed. The route class's remaining ~15.6 µs is not barrier count; packet 110's rank-3 "pruned top-10 network" idea is not pursued further without a new mechanism.

Evidence: `experiments/own-xpu-runtime/stage2/packet112-route-select/evidence/micro-B-{1,2}/samples.jsonl`.
