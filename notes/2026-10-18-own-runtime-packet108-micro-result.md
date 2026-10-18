# Packet 108 draft eight-value loads: micro below gate, closed (2026-10-18)

Lane B, card 2, `packet108-micro-B` 07:54–07:55 UTC, real captured routes replayed through the draft kernels, both orders, 0.85 time-ratio gate. Exact; no fault (count 2).

| Candidate | Time ratio (fused/production) | Qualified |
| --- | ---: | --- |
| draft-gate-load8 (K=2560) | **0.993** | no (every route stratum 0.978–0.995) |
| draft-down-load8 (K=640) | **0.901** | no |

At best the down change saves ~10% of a ~64 µs operator, about 6 µs per hit (~0.04%). Closed; packet 108's ranked levers 2 (IQ4 level lookup, p=0.15) and 3 (shared gate/up interleave) are smaller still and are not scheduled. The structural target remains launch/latency overhead (packet 109) and the head/draft splits (packets 105b/106b).

Evidence: `experiments/own-xpu-runtime/stage2/packet108-draft-loads/evidence/micro-B/qualification.json`.
