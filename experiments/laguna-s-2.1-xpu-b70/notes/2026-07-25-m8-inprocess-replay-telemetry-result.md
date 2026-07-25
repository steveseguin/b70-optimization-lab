# Laguna M8 in-process replay telemetry result

Date: 2026-07-25 America/Toronto

Status: **PASS; diagnostic-only timing evidence**.

Sealed internal-NVMe root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-17769a57d-8cf58ed0f-20260725T002351Z
```

Protocol commit: `17769a57d7de02e731899911ac76c41f60e3cb7a`.
Runtime identities remained vLLM
`8cf58ed0f3679245053b6f298b4bf1ccd13906ed` and kernels
`4772f727590c51b72add79350b913d098cf67872`.

## Gate result

The canonical q1 teacher, optimized eager DFlash, and optimized audited
Breakable-graph DFlash arms each ran in a fresh process and performed exactly
one greedy 272-token generation. All three reported `cached_tokens=0`,
`finish_reason=length`, and matched bitwise:

- token-ID SHA-256:
  `ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee`;
- text SHA-256:
  `d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f`.

Every campaign and per-arm worker report was empty. Every pre/post device-idle
snapshot passed. Models, caches, temporary files, logs, and evidence remained
on internal NVMe/ext4 below `/mnt/fast-ai`.

All four graph ranks closed exactly 31 profiles for
`BatchDescriptor(num_tokens=8)`. They agreed on 146 graph calls, 145 eager
boundaries partitioned into 97 collective and 48 attention calls, and segment
order SHA-256
`e5b64443ef499d8bb8b138a94ad504effeaa6434a8884ae9f885aecf12d34e1b`.

## Maximum-rank timing result

The analyzer selects the slowest rank independently for each timing field and
sample, then summarizes 31 samples. Median values are:

| Field | Median | p90 | Share of host total |
| --- | ---: | ---: | ---: |
| whole replay completion | 21.544 ms | 21.978 ms | n/a |
| replay host total | 16.724 ms | 17.943 ms | 100.0% |
| 48 attention boundary calls | 8.118 ms | 8.615 ms | 48.5% |
| 97 collective boundary calls | 6.080 ms | 6.327 ms | 36.4% |
| 146 graph replay calls | 2.097 ms | 2.306 ms | 12.5% |
| static-signature collect + compare | 0.360 ms | n/a | 2.2% |
| offloader sync | 0.001 ms | 0.002 ms | negligible |

The median aggregate per-call host costs are approximately 169.1 microseconds
per attention boundary, 62.7 microseconds per collective boundary, and
14.4 microseconds per graph replay call. Host submission is 77.6% of median
whole replay completion. These ratios use independently reduced max-rank
medians and are diagnostic prioritization signals, not an additive device
timeline.

Sample zero is a startup outlier at 40.711 ms whole completion, driven mostly
by a 23.870 ms post-replay synchronize. The median and p90 are stable despite
it. No sample was removed.

## Decision

The measurement rejects static-input validation as the first optimization:
collection plus comparison is only about 0.360 ms/replay, so even a large
relative improvement has a small end-to-end ceiling. The primary lane is now
reducing host overhead at the 48 attention boundaries without changing the
attention kernel, arithmetic, queue order, or exact graph topology. The
secondary lane is the 97 causally separated collective boundary submissions;
collective coalescing remains ruled out. Static-plan validation remains a
small, safe follow-up after the larger host paths.

This instrumented run is not throughput, endpoint, record, or LocalMaxxing
evidence. Its q1/eager/graph wall times include cold loading/JIT and graph-only
diagnostic synchronization and must not be compared with the approved
92.164 tok/s record.

Tracked structured summary:
`data/laguna-s-2.1-m8-inprocess-replay-telemetry-20260725.json`.
