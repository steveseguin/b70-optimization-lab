# 2026-06-27T20:17Z VDR2 Tight `p_min` Repeat

Goal: continue the Gemma 4 26B A4B Q8 one-B70 realistic-suite lane after the
VDR2 `89.45543282863798 tok/s` record by checking whether the tight
`p_min=0.0475` neighborhood repeats or improves under the fixed cold prompt
suite.

Promotion gate:

- fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- each prompt sent once as a cold response;
- `cached_tokens=0` every row;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram/history acceleration;
- target/verifier unchanged: `UD-Q8_K_XL`;
- Q4_0 MTP draft allowed only because accepted tokens are verified by the Q8
  target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT.

## Important Launch Mistake: `v20` Is Not Comparable

The first four-run sweep used the wrong harness variable names:

- used `SERVER_BIN=...` instead of `LLAMA_SERVER=...`;
- used `EXTRA_ARGS=...` instead of `EXTRA_LLAMA_ARGS=...`.

The harness therefore launched the default server:

`/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`

and `launcher_identity.extra_llama_args` was `null`. Those runs are strict
cold-suite measurements of the fallback launch identity, but they are **not**
VDR2/MTP p-min comparisons and must not be used as evidence that VDR2 regressed.

| Label | Median 1-100 after TTFT | Status |
| --- | ---: | --- |
| `gemma4-q8-gpu0-strict-vdr2-n3-p00450-ub1024-v20-20260627T201053Z` | 45.08814789189967 | wrong launch identity |
| `gemma4-q8-gpu1-strict-vdr2-n3-p004625-ub1024-v20-20260627T201053Z` | 44.909973715600216 | wrong launch identity |
| `gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v20-20260627T201053Z` | 45.09526681095578 | wrong launch identity |
| `gemma4-q8-gpu3-strict-vdr2-n3-p004875-ub1024-v20-20260627T201053Z` | 44.91946266844644 | wrong launch identity |

Keep these artifacts because they show why `LLAMA_SERVER` and
`EXTRA_LLAMA_ARGS` are mandatory for this harness.

## Corrected `v21` Sweep

Corrected invocation used:

- `LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- `EXTRA_LLAMA_ARGS` with `--spec-type draft-mtp`, Q4_0 MTP draft,
  `--spec-draft-n-max 3`, `--spec-draft-n-min 2`, variable
  `--spec-draft-p-min`, backend draft sampling disabled, f16 draft KV, and
  `--ctx-checkpoints 0`;
- `UBATCH_SIZE=1024`, `BATCH_SIZE=1024`, `CTX_SIZE=8192`, f16 target KV,
  `FLASH_ATTN=off`, `REASONING=off`;
- current VDR2 env stack:
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
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`.

| Label | `p_min` | Median 1-100 | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT median | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-strict-vdr2-n3-p00450-ub1024-v21-20260627T201757Z` | 0.0450 | 88.06323469748838 | 78.0633857735048 | 87.73605342605174 | 84.46414772436361 | 81.48255676262706 | 179.80360245564952 ms | strict pass |
| `gemma4-q8-gpu1-strict-vdr2-n3-p004625-ub1024-v21-20260627T201757Z` | 0.04625 | 89.43737321875525 | 81.12858654488201 | 89.6441285668689 | 83.83556050378711 | 81.32681482747452 | 180.77261501457542 ms | strict pass |
| `gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z` | 0.0475 | **90.32179401019857** | 86.02930423477346 | 92.1804554185734 | 86.21689344139463 | 83.21177427158659 | 179.68109803041443 ms | **new strict record** |
| `gemma4-q8-gpu3-strict-vdr2-n3-p004875-ub1024-v21-20260627T201757Z` | 0.04875 | 85.90621112154868 | 81.28957617728382 | 86.9564612856055 | 83.27168284603204 | 80.16542003121401 | 179.87088399240747 ms | strict pass |

All corrected rows passed `realistic_final_gate.passed=true` and had
`cached_tokens=0` on every prompt.

## Promotion

The GPU2 `p_min=0.0475` repeat is the new policy-compliant one-B70 Q8 record:

- summary:
  `data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`;
- LocalMaxxing payload:
  `data/localmaxxing-payloads/gemma4-q8-vdr2-p00475-v21-20260627T201757.json`;
- LocalMaxxing response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v21-20260627.submit.log`;
- LocalMaxxing ID: `cmqwt1zk803ozqr01hctqss2z`.

This supersedes the previous VDR2 `89.45543282863798 tok/s` submission
`cmqwqzayr03o8qr01j6lgx93n`, while keeping that result as valid supporting
evidence.

## Next Actions

- Treat `90.32179401019857 tok/s` as the new strict threshold to beat.
- For more p-min exploration, keep using `LLAMA_SERVER` and
  `EXTRA_LLAMA_ARGS`; do not use `SERVER_BIN` or `EXTRA_ARGS`.
- Further progress likely needs reducing target/verifier MoE or LM-head cost,
  improving fresh-valid speculation, or adding a structural verifier shortcut.
  Small p-min sweeps can still find variance wins, but the lane is now at a
  tight frontier.
