# Packet174 result: the fill kick is neutral; the slow readback is copy-engine serialization, not submission timing

Card 0, whole host, QUIET set. `packet174-v5-A` ran 11:03–11:16 UTC. GPU fault count stayed 2.

| View | Arm | tok/s | slow-readback fraction | transfer wall ms/token |
| --- | --- | ---: | ---: | ---: |
| A0 | spin (warm-up, excluded) | 34.467 | 0.401 | 1.188 |
| B0 | spin + fill kick | 34.559 | 0.402 | 1.180 |
| A1 | spin | 34.564 | 0.403 | 1.183 |
| B1 | spin + fill kick | 34.564 | 0.402 | 1.180 |
| A2 | spin | 34.567 | 0.405 | 1.185 |

All 60 requests are exact vs `iq3-p49-split32-v1`, and drift is 0.007%. The minimum gain is **−0.02%**, so `candidate_beats_all_controls` is false. **Closed.**

**Reading:** a non-blocking `zeCommandListHostSynchronize(maintenance, 0)` after each fill batch changes nothing, so the fills were already submitted promptly. The 1.07 ms/token cost follows packet174's law: fill bytes drain ahead of the 8-byte token readback at 0.035 ms/MB. It therefore comes from the readback serializing behind fill bytes on the hardware copy engine. This also explains why packet171b's compute-queue memcpy was neutral: the driver most likely offloads in-order queue memcpy to a copy engine as well.

**Next:** packet176 moves the token readback off every copy engine. A compute kernel stores the token straight into host-visible memory, and the host reads it after the compute event completes. It is in preparation behind this run, with packet58as as the parent.
