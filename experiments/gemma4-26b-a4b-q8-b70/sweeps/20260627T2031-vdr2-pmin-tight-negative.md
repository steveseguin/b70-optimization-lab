# 2026-06-27T20:31Z VDR2 Tight `p_min` Negative

Goal: continue from the strict `90.32179401019857 tok/s` VDR2 record by
checking whether a tighter `p_min` neighborhood around `0.0475` repeats or
improves under the fixed realistic cold prompt suite.

This was a full strict sweep, not a synthetic diagnostic:

- fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- each prompt sent once as a cold response;
- `cached_tokens=0` every row;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram/history acceleration;
- target/verifier unchanged: `UD-Q8_K_XL`;
- Q4_0 MTP draft tokens verified by the Q8 target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT.

Run identity:

- llama.cpp server:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- `n_max=3`, `n_min=2`, `UBATCH_SIZE=1024`, f16 target/draft KV,
  `--ctx-checkpoints 0`;
- VDR2 env stack matched the `20260627T2017` record lane, including
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`, and
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`.

## Results

| Label | `p_min` | Median 1-100 | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT median | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-strict-vdr2-n3-p004725-ub1024-v22-20260627T203148Z` | 0.04725 | 88.971548 | 83.426168 | 89.420027 | 84.913265 | 81.926533 | 179.729 ms | strict pass, below record |
| `gemma4-q8-gpu1-strict-vdr2-n3-p0047375-ub1024-v22-20260627T203148Z` | 0.047375 | 85.732692 | 80.301950 | 87.173288 | 83.520416 | 81.045119 | 180.260 ms | strict pass, below record |
| `gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat2-ub1024-v22-20260627T203148Z` | 0.0475 | 87.144002 | 79.698190 | 86.510662 | 84.049028 | 80.912178 | 180.844 ms | strict pass, repeat variance loss |
| `gemma4-q8-gpu3-strict-vdr2-n3-p0047625-ub1024-v22-20260627T203148Z` | 0.047625 | 84.418406 | 77.252416 | 86.306865 | 82.204557 | 78.955216 | 180.281 ms | strict pass, below record |

All rows passed `realistic_final_gate.passed=true` and had `cached_tokens=0`.

## Conclusion

No row beat the current `90.32179401019857 tok/s` strict record. The exact
`p_min=0.0475` repeat fell to `87.144002 tok/s`, so the record row likely sits
near the high side of normal run variance. Do not keep spending full strict
sweeps on tiny `p_min` deltas alone unless there is a new code/runtime change
that materially changes acceptance or target verifier cost.

Next work should pivot to higher-ROI structural candidates: reduce verifier
MoE/LM-head cost, improve fresh-valid speculation, or add a structural verifier
shortcut that still preserves the Q8 target/verifier gate.
