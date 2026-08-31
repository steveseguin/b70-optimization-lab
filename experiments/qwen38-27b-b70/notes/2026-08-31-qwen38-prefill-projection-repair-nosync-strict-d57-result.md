# Qwen3.8 no-barrier strict D57 result

D57 passed every strict correctness gate and improved prefill latency.

- All 12 full token-ID sequences exactly matched synchronized D54.
- Cached tokens were zero, all canaries passed, and the eight-repeat canary had
  one output class.
- Median TTFT fell from 380.687002 ms to 310.378243 ms: **70.309 ms (18.5%)**.
- The class-balanced decode median was 24.555147 tok/s, versus 24.804756 and
  24.801498 in D54/D55. Decode never enters the changed branch, so this isolated
  run is insufficient to attribute the ~1% movement; a later replay will bound
  variance.

The no-barrier implementation becomes the preferred correctness candidate, but
is not yet promoted as the final fast lane. D58 tests stable M=128 padding for
short prefills before TP2/MTP restoration.
