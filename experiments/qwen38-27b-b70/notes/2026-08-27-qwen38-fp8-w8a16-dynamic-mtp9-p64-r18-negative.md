# Qwen3.8 FP8 dynamic MTP9 p64 recovery R18 negative

Limiting the MTP9 service from 128 to 64 scheduler slots did not recover its
aggregate rate. The preregistered treatment is closed negative.

| Shape | promoted MTP8 median | MTP9 p64 R18 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 146.814418 | **158.728062** | **+8.11%** |
| c64 aggregate decode | **1,094.314767** | 806.950345 | **-26.26%** |

Startup still allocated exactly 4,062 KV tokens and reported 15.87x nominal
concurrency for 256-token requests—the same capacity as the failed p128 R17
service. The declared p64 batch missed its 1,072.428472 tok/s gate by 24.75%,
so the protocol stopped before the 512-request canary.

The batch returned all 8,192 tokens with complete IDs, cache zero, and no
cross-base collisions. C2 isolation, 7/7 sequential exact cases, 8/8 repeat
stability, frozen-baseline agreement, final health, zero exit, and no OOM all
passed. MTP8 remains the selected balanced profile. The next useful work would
need to change the depth-driven cache reservation or draft execution itself;
another scheduler-slot cap is not justified by this evidence.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp9-p64-dynamic-mtp1-20260827-r18/`](../data/qwen38-fp8-w8a16-mtp9-p64-dynamic-mtp1-20260827-r18/).
No missing shape is inferred, interpolated, or extrapolated.
