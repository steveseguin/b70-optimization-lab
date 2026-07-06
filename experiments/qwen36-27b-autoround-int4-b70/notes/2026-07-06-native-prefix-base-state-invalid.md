# 2026-07-06 - Native prefix-base GDN state contract is still invalid at endpoint

## Context

The current valid Qwen27 record remains
`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound` with the
runtime target INT8 LM-head using BF16 scales, MTP3, XPU graph capture size 8,
and the strict fresh realistic suite. Draft-INT4/native GDN paths have repeatedly
screened faster (`~68-72 tok/s`) but failed repeat/order quality.

This experiment tested whether the native packed GDN speculative state table was
off by one because it stored `state after spec row j` in column `j` without a
separate base column. The patch added a gated
`VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1` layout:

- column `0` is the unmodified selected base/running state;
- exact state after spec row `j` is stored in column `j + 1`;
- accepted-source selection uses `num_accepted_tokens` instead of
  `num_accepted_tokens - 1`;
- conv column `0` is restored from the saved base state after exact stores.

Patch snapshot:
`patches/qwen36-27b-autoround-int4-b70/qwen27-native-prefix-base-invalid-20260706.patch`.

## Build/runtime hygiene

The active `vllm_xpu_kernels` package had been contaminated by a oneAPI 2026
build that required `libsycl.so.9`, while the active PyTorch XPU runtime is on
`libsycl.so.8`. That caused vLLM startup to fail with device inference and FA2
extension errors.

Repair performed before endpoint testing:

- restored `_C.abi3.so` and `_moe_C.abi3.so` from known-good `libsycl8`
  artifacts;
- rebuilt/copied `_xpu_C.abi3.so`, `libgdn_attn_kernels_xe_2.so`, and
  `libgrouped_gemm_xe_2.so` with oneAPI 2025.3;
- restored FA2/attention support libraries from the sycl8 digest;
- verified no active extension still declares `NEEDED libsycl.so.9`;
- verified `VLLM_TARGET_DEVICE=xpu` imports and FA2 exposes `varlen_fwd`.

The candidate launcher now records `VLLM_TARGET_DEVICE=xpu`,
`VLLM_XPU_KERNELS_SRC`, and prepends the active XPU kernels package to
`LD_LIBRARY_PATH`.

## Native contract checks

The standalone native checker passed both default and prefix-base contracts:

- default packed layout:
  `scripts/check-gdn-native-spec-prefix.py --device xpu:0 --num-reqs 2 --spec-len 4 --head-k-dim 32 --head-v-dim 16`
  -> `passed: true`, accepted source columns `[0, 0]` and `[0, 1]`;
- prefix-base layout:
  `VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1 ... --prefix-base-state --num-reqs 3 --spec-len 5 --head-k-dim 64 --head-v-dim 32`
  -> `passed: true`, accepted source columns `[1, 1, 1]` and `[1, 2, 3]`.

This proves the local kernel contract was internally consistent, but endpoint
quality still failed.

## Endpoint run

Label: `qwen27-draftint4-native-prefixbase-20260706T023307Z`

Important identity:

- model:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 GPU, TP1, max model len 2048, max seqs 1;
- MTP3 via `qwen3_next_mtp`;
- XPU graph `PIECEWISE`, `max_cudagraph_capture_size=8`;
- target runtime INT8 LM-head with BF16 scales;
- draft INT4 LM-head, group size 128, BF16 scales;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1`.

Artifacts:

- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-realistic128-chat-tokenids-qwensuite-20260706T023307Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-native-prefixbase-repeat64-ctx1024-20260706T023307Z.json`;
- candidate summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-candidate-summary-20260706T023307Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-20260706T023307Z`.

## Result

Strict fresh speed passed the benchmark policy but quality failed:

- cached tokens: all zero;
- each prompt run once;
- median tokens 1-100 after TTFT: `68.99085877682683 tok/s`;
- p10: `60.1354755320144`;
- mean: `68.39600917245922`;
- median TTFT: `488.672 ms`;
- smoke: pass;
- exact quality cases: pass for `OK`, copy phrase, arithmetic, and JSON fields;
- repeat64 quality: fail.

Repeat output was unstable and mostly wrong relative to the baseline:

- baseline repeat output is stable: `blue, green, red, yellow`;
- candidate produced multiple outputs, including `blue, green, red, yellow`,
  truncated `blue, green, red`, `blue, green, green`,
  `blue, green, red, yellow, black`, and runaway yellow/comma repetition.

This is not promotable and must not be submitted to LocalMaxxing.

## Interpretation

The prefix-base state-table layout fixes an internally plausible off-by-one
contract but does not fix the endpoint transaction. The real problem is still
the interaction between target-verified speculative acceptance and GDN state
commit/rollback in the fast native path.

The useful conclusion is negative:

- do not keep sweeping simple source-column/layout variants for this lane;
- the endpoint failure is likely in the accepted-prefix transaction as a whole,
  not just the selected source column;
- future work should either make the fast path use a ReplaySSM/tape-style exact
  commit transaction, or move effort to a different acceleration route such as
  DFlash acceptance/draft architecture or fused verifier work.

## Follow-up: prefix-base v2 with Python offset parity

After the first endpoint run, we found one real inconsistency in the experiment:
the native XPU kernel selected prefix-base source column `N`, but the Python-side
GDN helpers still treated accepted-source offsets as `N - 1` unless the separate
`VLLM_XPU_GDN_SPEC_STATE_OFFSET_PLUS_ONE=1` flag was also set. A v2 patch made
`VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1` imply plus-one semantics in:

- `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
  (`_xpu_gdn_spec_state_offset_plus_one_enabled`);
- `vllm/v1/attention/backends/gdn_attn.py` (non-spec promote-source metadata).

Patch snapshot:
`patches/qwen36-27b-autoround-int4-b70/qwen27-native-prefix-base-v2-invalid-20260706.patch`.

Run:
`qwen27-draftint4-native-prefixbase-v2-20260706T024158Z`

Artifacts:

- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-v2-realistic128-chat-tokenids-qwensuite-20260706T024158Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-native-prefixbase-v2-repeat64-ctx1024-20260706T024158Z.json`;
- candidate summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-v2-candidate-summary-20260706T024158Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-v2-20260706T024158Z`.

Result:

- strict fresh median: `67.06803514558703 tok/s`, p10 `59.729189560718574`,
  mean `66.30312543383671`;
- cached tokens: all zero;
- exact quality cases: pass for required fields;
- repeat64: **fail**.

Repeat64 distribution:

- `47/64` `blue, green, red, yellow` (baseline text);
- `9/64` `blue, green, red`;
- `7/64` `blue, green, red, yellow, black`;
- `1/64` runaway color repetition.

Conclusion: prefix-base plus Python offset parity improves the signature versus
v1 but remains invalid. This closes simple source-column / prefix-base table
layout changes as a path to a promotable fast native result. The missing piece
is still an exact accepted-prefix GDN/DeltaNet transaction, not another
offset-selection flag.

## Follow-up: prefix-base v3 tried to add the missing base column

After v2, the remaining obvious hypothesis was that the endpoint did not have
enough state columns for the intended prefix-base contract. The synthetic
checker used `spec_len=5` for MTP3-style four verifier rows:

- column `0`: selected base/running state;
- columns `1..4`: exact state after verifier rows `0..3`.

The endpoint, however, still exposed only **four** block-table columns for MTP3:

```json
{
  "num_spec_decodes": 1,
  "num_spec_decode_tokens": 4,
  "num_actual_tokens": 4,
  "max_query_len": 4,
  "spec_state_cols": 4,
  "num_decode_draft_tokens_cpu": {"head": [3], "shape": [1]},
  "block_table_tensor": {"head": [1, 2, 3, 4], "shape": [1, 4]}
}
```

v3 attempted to plumb an extra metadata column and shifted Python-side publish
helpers to write prefix state to `state_col + 1`. Under the real allocator this
still clamped to four columns, then the first smoke request device-lost during
the next `_prepare_inputs()` event synchronization:

`RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)`.

Run:
`qwen27-draftint4-native-prefixbase-v3-20260706T024850Z`

Artifacts:

- candidate summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-v3-candidate-summary-20260706T024850Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-v3-20260706T024850Z`.

Diagnostic trace:
`qwen27-draftint4-native-prefixbase-v3-metatrace-20260706Tdiagv3meta025459`

- trace file:
  `/tmp/qwen27-prefixbase-v3-metadata-20260706Tdiagv3meta025459.jsonl`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-v3-metatrace-20260706Tdiagv3meta025459`.

Conclusion: v3 confirms the synthetic prefix-base checker was over-permissive
relative to real vLLM state allocation. A true prefix-base implementation would
need allocator/block-table changes to provide `num_spec + 2` state columns, and
would still need the broader accepted-prefix transaction fixed. That is too
large for this already-negative lane, so prefix-base is closed as **invalid /
not promotable**. Preserve the patch as a reference, but do not continue simple
source-column or metadata-column sweeps.
