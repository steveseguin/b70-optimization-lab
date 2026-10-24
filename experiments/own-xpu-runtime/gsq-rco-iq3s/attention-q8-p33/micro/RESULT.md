# Exact attention kernel comparison

On October 24 at 07:02 UTC, one B70 owner completed all 84 fixed pairs and 168
kernel submissions. Every output matched both the other arm and the full saved
baseline output bytes. Independent readback passed. Twelve preregistered warmup
pairs are excluded; all 72 measured pairs remain, without outlier filtering.

| Fixed layer | Measured pairs | Control median µs | Candidate median µs | Sum candidate / control |
| --- | ---: | ---: | ---: | ---: |
| 0 | 24 | 304.063 | 63.282 | 0.21494 |
| 23 | 24 | 303.230 | 63.282 | 0.21420 |
| 47 | 24 | 304.479 | 63.490 | 0.21323 |

Across all cases the summed ratio is 0.21412. Both orders retain the advantage:
AB 0.20975 and BA 0.21878, with 36 measured pairs each. The control is original
packed Q8 p6; the candidate is existing p33 variant6/split1. Exact weights,
BF16 inputs/output conversion, accumulation and reduction are preserved.

This measures repeated isolated projection GPU event latency with natural cache
state, three fixed real saved inputs and one profiling queue. It excludes host
enqueue, uploads and readback. It is not full-model throughput, a cold response
benchmark, a general-context result or a speed record. The larger expanded
representation costs 45 MiB per rank at all 48 model sites. Full candidate
correctness still requires the five missing prompt pairs from the interrupted
model run; the seven completed pairs retain their separate audited evidence.

Native teardown completed with no live allocations or in-flight work; physical
card drain, unchanged vision ownership and unchanged historical fault baseline
were observed. No stop signal, retry, service operation or settings change.

- [Independent actual-device review](evidence/device-a/review.json), SHA256
  `61abfcb999ddf213f8559c0b99734c1ef85baaffbf9d7dffa70acaec0155280d`.
- [Frozen operating plan](evidence/operating-plan.json).
- [Native build identity](evidence/native-build.json).
- [Preregistered method](README.md).
- Complete local raw evidence: `/home/steve/own-xpu-runtime-results/gsq-attention-micro-a`.

The preparation README and source receipts retain their original prospective
wording and hashes; this result records the subsequent admitted execution.
