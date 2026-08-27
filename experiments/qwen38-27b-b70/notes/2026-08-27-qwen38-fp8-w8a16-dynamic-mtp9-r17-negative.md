# Qwen3.8 FP8 dynamic MTP9 R17 aggregate-gate negative

The preregistered MTP9-at-one/MTP1-at-load treatment is closed negative. It
improved the eligible fresh single-user result to **158.602110 tok/s**, 8.03%
above the promoted MTP8 median, but its declared c64 batch reached only
**889.607586 aggregate tok/s**.

| Shape | promoted MTP8 median | MTP9 R17 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 146.814418 | **158.602110** | **+8.03%** |
| c64 aggregate decode | **1,094.314767** | 889.607586 | **-18.71%** |

The c64 result missed the preregistered 1,072.428472 tok/s floor by 17.05%,
so the ordered protocol stopped before the 512-request semantic canary. The
declared batch nevertheless returned all 8,192 completion tokens with complete
IDs, zero cached tokens, and zero cross-base collisions. C2 isolation, 7/7
sequential exact cases, 8/8 repeat stability, and frozen-baseline agreement
all passed.

MTP8 remains the selected balanced service. The higher MTP9 singleton rate is
not spliced into that profile because the exact MTP9 service failed its
aggregate-retention gate. Docker reported exit zero and no OOM. The container
entered removal before the post-stop log request, so the full pre-stop log and
final inspect receipt are preserved with that capture limitation stated
explicitly.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp9-dynamic-mtp1-20260827-r17/`](../data/qwen38-fp8-w8a16-mtp9-dynamic-mtp1-20260827-r17/).
No missing shape is inferred, interpolated, or extrapolated.
