# Qwen3.8 FP8 dynamic MTP9 reset-after-free latch R20 negative

The corrected latch restored the MTP9 singleton gain, but it made aggregate
throughput worse and did not preserve concurrent output identity. The exact
treatment is closed negative.

| Shape | promoted MTP8 median | latch R20 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 146.814418 | **157.939541** | **+7.58%** |
| c64 aggregate decode | **1,094.314767** | 866.085639 | **-20.86%** |

The eligible singleton exceeded its 149.750706 tok/s gate, proving the
reset-after-final-free correction worked. The excluded transition measured
827.856893 tok/s with 58/64 sequential-oracle matches. The declared c64 batch
returned all 8,192 tokens with complete IDs, cache zero, and no cross-base
collisions, but reached only 866.085639 tok/s and 57/64 oracle matches. It
missed the 1,072.428472 gate by 19.24%, so the ordered protocol stopped before
the 512-request canary.

This falsifies the tail hypothesis. An unlatched MTP9 service switches its
last active request from MTP1 to the much faster MTP9 singleton path. Keeping
the draining batch on MTP1 removed that helpful acceleration and was 2.64%
slower than unlatched R17. The larger MTP9 cache reservation and concurrent
execution remain the relevant costs; another busy-period-latch variant is not
justified. MTP8 remains the selected balanced profile.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp9-latch2-dynamic-mtp1-20260827-r20/`](../data/qwen38-fp8-w8a16-mtp9-latch2-dynamic-mtp1-20260827-r20/).
No missing shape is inferred, interpolated, or extrapolated.
