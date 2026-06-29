# 2026-06-28T1233 - BF16 MUL_MAT_ID direct multi-token branch

Status: **closed negative**

Goal: crack reliable `>100 tok/s` for Gemma 4 26B A4B UD-Q8_K_XL on one B70
using the strict fresh-response realistic suite. Runtime-only sweeps were
clustering at `98-99 tok/s`, so this branch targets verifier/target-body MoE
overhead.

Patch summary:

- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/ggml-sycl.cpp`;
- new default-off env:
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1`;
- adds a direct BF16 multi-token `MUL_MAT_ID` path for
  `src1=[ncols,1,n_tokens]`, `ids=[n_experts_used,n_tokens]`,
  `n_tokens<=8`, `n_experts_used<=8`;
- records the env in:
  `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-first-baseline.sh`;
- records the env in replica launch logs:
  `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-llamacpp-replica.sh`.

Initial strict 128-token screen:

| Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| control | `92.571` | `86.122` | `95.639` | `95.704` | valid/cached0 | `data/gemma4-q8-gpu0-bf16direct-control-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| BF16 direct, broad | `97.937` | `87.226` | `96.934` | `95.691` | valid/cached0 | `data/gemma4-q8-gpu1-bf16direct-broad-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| BF16 direct, `ffn_moe_gate_up-29` only | `90.421` | `78.892` | `89.176` | `85.644` | valid/cached0 | `data/gemma4-q8-gpu2-bf16direct-gateup29-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| BF16 direct, `ffn_moe_down-29` only | `90.836` | `80.108` | `89.554` | `88.162` | valid/cached0 | `data/gemma4-q8-gpu3-bf16direct-down29-128-20260628T123359Z-bf16direct-screen3/summary.json` |

Initial decision:

- Not promotable: broad lane did not beat the current promoted `98.340` record;
  targeted lanes were clear losses.
- Do not submit to LocalMaxxing.

Review findings and follow-up:

- Add an upper-bound guard for `expert_id >= src0->ne[2]` before indexing
  expert weights.
- Add explicit `src1` stride checks.
- Add BF16 direct to SYCL graph eligibility, otherwise the enabled path may
  force graph fallback and make the initial screen unfair.

Graph-safe retest (`20260628T124630Z-bf16direct-graphsafe-paired`):

| Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| control GPU0 | `99.519` | `87.055` | `96.775` | `94.661` | valid/cached0 | `data/gemma4-q8-gpu0-bf16graphsafe-control-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| BF16 direct GPU1 | `96.208` | `87.059` | `96.859` | `96.461` | valid/cached0 | `data/gemma4-q8-gpu1-bf16graphsafe-broad-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| control GPU2 | `95.818` | `84.920` | `94.384` | `94.757` | valid/cached0 | `data/gemma4-q8-gpu2-bf16graphsafe-control-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| BF16 direct GPU3 | `97.722` | `86.277` | `97.446` | `95.597` | valid/cached0 | `data/gemma4-q8-gpu3-bf16graphsafe-broad-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |

Final decision:

- Closed negative. BF16 direct is validity-safe and default-off after the
  guard/graph-eligibility fixes, but it does not beat paired controls or the
  promoted `98.340` full512 record.
- Do not promote or submit to LocalMaxxing.
- Keep this note and patch context so the BF16 `MUL_MAT_ID` lane is not
  rediscovered as a likely `>100` path without a materially different kernel.
