# Raw-Q8 attention/combine epilogue (card 27)

The candidate retained the raw Q8 GEMV and attention stores while updating four HC streams in the same launch, then
skipped 23 separate `attn.combine` launches. CPU finite/guard tests passed. Every one of three full A/B comparisons
matched all 1,029 target buffers and 71 draft allocations, with identical draft tokens; zero GPU faults.

The first timing sequence accidentally retained `OWNRT_DECODE_PROFILE=2` and is not a speed result. The final sequence
used `OWNRT_DECODE_PROFILE=0` for both arms:

| Pair | Reference ms/half | Candidate ms/half | Candidate − reference |
|---|---:|---:|---:|
| 1 | 10.636 | 11.486 | +0.850 ms |
| 2 | 10.634 | 11.449 | +0.814 ms |
| 3 | 10.647 | 11.472 | +0.825 ms |

Median paired cost: **+0.825 ms/half**. The added epilogue/barrier costs much more than the roughly 0.112 ms launch and
readback budget. The lever is closed negatively and was not integrated. `attention-fuse.patch` and the CPU evidence
remain for review; do not use the earlier profiled timings as a benchmark.
