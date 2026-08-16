# Qwen3.8 27B Q8 structural feasibility and sampling audit

Date: 2026-08-16  
Host: 2x ASRock Intel Arc Pro B70, 32 GiB per card; 16 GiB host RAM  
Scope: target-only Q8_0, F16 KV, equal TP2, no MTP/DFlash/speculation

## Outcome

Three tempting structural shortcuts were audited without changing the promoted
Qwen3.8 target or accepted source:

1. Lossless byte packing of the existing Q8 values does not have enough
   practical redundancy. Simple GPU-decodable exception formats expand the
   weights, while an ideal entropy coder could save only about 3.9% of the Q8
   payload before metadata and decode cost.
2. Qwen3.8 executes **128** fused TP2 all-reduces per generated token. Every
   one already reaches the combined all-reduce + residual add + RMS norm +
   multiply path. The transferred vectors total only about 2.5 MiB/token, so
   this is a synchronization problem rather than a PCIe-bandwidth problem.
3. llama.cpp backend sampling is explicitly unsupported for tensor split in
   this source. Requests spelling `"backend_sampling": true` logged
   `backend sampling not supported with SPLIT_MODE_TENSOR; using CPU`; the
   apparent arms were therefore identical CPU-sampling runs, not an A/B test.

No performance change is promoted from this audit.

## Lossless Q8 packing sample

The streaming analysis covered the gate, up and down Q8_0 tensors for layers
0 through 7:

- 24 tensors;
- 2,272,788,480 encoded bytes;
- 66,846,720 Q8 blocks;
- 2,139,095,040 signed Q values;
- symbol entropy: 7.684765 bits/value.

Each ordinary Q8_0 block is 34 bytes: 32 signed values plus a two-byte scale.
Sentinel-plus-exception layouts preserve every value but measured:

| Packed values | Mean bytes/block | Change vs 34-byte Q8_0 block |
| --- | ---: | ---: |
| 5-bit + exceptions | 46.748733 | +37.496% |
| 6-bit + exceptions | 43.951615 | +29.269% |
| 7-bit + exceptions | 38.065849 | +11.958% |

The entropy lower bound for the 32 Q values is 30.739 bytes, or 32.739 bytes
including the unchanged scale: only about 3.71% below 34 bytes. That idealized
bound excludes tables, restart points, random-access alignment and GPU decode
instructions. It cannot plausibly close the roughly 8.7% bandwidth gap from
the current Q8 result to 40 tok/s.

Raw analysis:

`/mnt/fast-ai/bench-results/qwen38-q8-lossless-pack-analysis-20260816.txt`

SHA-256: `436dc023752d8712ecdc04c35ec7314a9dc958dd6ba9a3dfa99a695b65bd10d0`

## TP2 collective structure

A bounded `p0/n1` count-only run set `GGML_META_ALLREDUCE_STATS=1`. It did not
enable the unsafe SYCL profiler, device timestamps or extra device barriers.
Both graph executions reported:

```text
allreduce=128 fused_allreduce_add=128 fused_allreduce_add_rms_mul=128
```

The smoke completed at 37.151243 tok/s, reported `VERIFY_MISMATCH=0`, and left
both GPUs normal. Each full hidden vector is 5,120 FP32 values (20 KiB), so 128
boundaries move about 2.5 MiB/token. Replacing full hidden vectors with a
persistent shard would not remove the exact cross-device dependency: every
RMS normalization still needs the combined sum of squares, and subsequent
projections need both activation shards. This would be a broad execution-
topology rewrite with substantial quality and reliability risk, not a small
bandwidth optimization.

Raw census:

`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-collective-structure/allreduce-census-p0-n1.log`

SHA-256: `4fdd00258c01469bea22c0dfe30a46f23efdcc439cbc2f16c4fcb09eef02e5d8`

## Backend-sampling audit

Three complete cache-zero endpoint suites were collected against the same
loaded DP4A2 server. All 12 complete output hashes matched the promoted Q8
oracle in every run. However, the server logged the tensor-split fallback for
each requested backend-sampling arm, so the following values measure ordinary
process warm-up/state only:

| Request spelling | Legacy median | Conventional median | Full-512 median |
| --- | ---: | ---: | ---: |
| backend requested, first | 37.123179 | 36.751947 | 36.605504 |
| CPU sampling control | 37.800053 | 37.422053 | 37.509355 |
| backend requested, warmed | 37.798759 | 37.420771 | 37.507967 |

The last two rows are effectively identical because both used CPU sampling.
They must not be cited as a backend-sampling gain or as an independent source
record. The first row also shows why process state must be balanced before
attributing small changes.

Raw JSON is under:

`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-backend-sampling/`

## Decision and next exact target

Keep the accepted fused TP2 collective and ordinary Q8 bytes. The next narrow
service experiment is tensor-split-aware greedy sampling: compute an exact
local `(logit, vocabulary_index)` winner on each rank, compare the two winners
with the same tie rule, and return only the selected token. It must fail closed
for non-greedy samplers and pass 12/12 output hashes plus a matched endpoint
screen. This can remove full-logit host sampling traffic, but its realistic
ceiling is sub-percent; it is incremental work, not the complete route to
40 tok/s.
