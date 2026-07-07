# 2026-07-07 - ReplaySSM state digest trace

## Context

Current valid Qwen27 headline remains the webhie AutoRound W4A16 lane with
runtime INT8 target LM-head BF16 scales, runtime INT4 draft LM-head BF16
scales, ReplaySSM exact GDN state handling, commit-in-forward, MTP3/cg8, and
strict fresh median `68.236 tok/s`.

The previous target-body timing screen showed the obvious remaining waste is
not wrapper-level LM-head work.  For the current ReplaySSM lane, the useful
source-level next step is better visibility into the exact GDN/DeltaNet state
transaction boundaries before mutating endpoint behavior again.

## Patch

Patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-state-digest-trace-20260707.patch`

Important caveat: this patch artifact is a cumulative diff of
`vllm/model_executor/layers/mamba/gdn_linear_attn.py` against the local active
vLLM Qwen branch, not a clean upstream patch.  The new behavior added in this
pass is default-off diagnostic tracing only:

- extend `_gdn_replayssm_commit_trace` so it can optionally include small
  digests for `conv_state`, ReplaySSM `d_cache`, `k_cache`, `g_cache`, and
  `conv_pending`;
- add `VLLM_XPU_GDN_ROW_TRACE_REPLAYSSM_STATE=1` as the extra gate for those
  state digests;
- emit trace records at:
  - `replayssm_commit_pending_before`;
  - `replayssm_commit_pending_after`;
  - `replayssm_after_stage_conv`;
  - `replayssm_after_spec_decode`.

Normal endpoint behavior is unchanged unless the existing GDN row trace file is
enabled and the new state-digest flag is set.

New summarizer:

- `scripts/summarize-qwen27-replayssm-state-trace.py`

## Validation

Unit/contract checks after the patch:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py \
  --device xpu:0 --num-reqs 2 --spec-len 3 --heads 2 --dim 8
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-replayssm-commit-pending.py \
  --device xpu:0
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py \
  --device xpu:0
```

Results:

- accepted-prefix synthetic contract: pass;
- ReplaySSM `commit_pending` native-vs-reference: pass;
- native packed-prefix contract: pass.

Trace diagnostic command shape:

```bash
LABEL=qwen27-replayssm-state-digest-trace-20260707T041855Z \
STAMP=20260707T041855Z \
RUN_ROOT=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics \
GPU_INDEX=0 PORT=19420 RUN_QUALITY=0 QUALITY_SKIP_LONG_CONTEXT=1 \
VLLM_XPU_GDN_ROW_TRACE_FILE=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-replayssm-state-digest-trace-20260707T041855Z-20260707T041855Z/gdn-replayssm-state-trace.jsonl \
VLLM_XPU_GDN_ROW_TRACE_REPLAYSSM_STATE=1 \
VLLM_XPU_GDN_ROW_TRACE_RANK=0 \
VLLM_XPU_GDN_ROW_TRACE_LAYERS=0 \
VLLM_XPU_GDN_ROW_TRACE_STAGES=replayssm_commit_pending_before,replayssm_commit_pending_after,replayssm_after_stage_conv,replayssm_after_spec_decode \
VLLM_XPU_GDN_ROW_TRACE_MAX_LINES=80 \
VLLM_XPU_GDN_ROW_TRACE_STATE_LIMIT=1 \
VLLM_XPU_GDN_ROW_TRACE_STATE_HEAD=4 \
VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8 \
VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1 \
VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

Diagnostic result:

- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-replayssm-state-digest-trace-20260707T041855Z-20260707T041855Z`;
- candidate summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-state-digest-trace-20260707T041855Z-candidate-summary-20260707T041855Z.json`;
- trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-replayssm-state-digest-trace-20260707T041855Z-20260707T041855Z/gdn-replayssm-state-trace.jsonl`;
- promoted compact summaries:
  - `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-state-digest-trace-20260707T041855Z-summary.json`;
  - `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-state-digest-trace-20260707T041855Z-summary.md`.

Endpoint status:

- strict fresh mechanics passed: fixed Qwen realistic suite, each prompt once,
  `cached_tokens=0` for all 12 requests;
- median diagnostic throughput `67.453 tok/s`, mean `67.989`, p10 `62.664`;
- quality intentionally skipped;
- diagnostic only, no LocalMaxxing submission.

Trace coverage:

- 80 records total, layer `language_model.model.layers.0.linear_attn`;
- 20 records each for `replayssm_commit_pending_before`,
  `replayssm_commit_pending_after`, `replayssm_after_stage_conv`, and
  `replayssm_after_spec_decode`;
- state digests present in all 80 records for `conv_state`, `conv_pending`,
  `d_cache`, `k_cache`, and `g_cache`.

## Interpretation

This is not a speed optimization by itself.  It gives the next source-level
agent concrete visibility into the ReplaySSM transaction boundaries:

1. commit previous pending state at the next forward;
2. stage current conv rows into `conv_pending`;
3. run `gdn_replayssm_spec_decode` into ring-cache state;
4. mark pending and pending length for the next commit.

The trace confirms the records are available with bounded overhead and without
changing endpoint behavior.  Use this when developing a graph-safe GDN/DeltaNet
transaction or when comparing ReplaySSM against a future native prefix/tape
implementation.

## Native packed-spec note

A parallel explorer audit found the smallest non-mutating native packed-spec
prefix digest hook is in `/home/steve/src/vllm/vllm/_xpu_ops.py`, inside
`_gdn_attention_core_xpu_impl`, immediately before and after
`torch.ops._xpu_C.gdn_attention_spec_decode`.  That hook is for the older native
packed-spec path, not the current valid ReplaySSM record path.  If reopening the
invalid fast native family, trace prefix 0 before the native call and prefixes
1..k after the call; do not infer prefix 0 after the call because native column
0 is overwritten by row-0 prefix state in the default contract.

## Next

Use the state digest trace to guide a real graph-safe transaction/tape patch.
Do not spend more endpoint runs on wrapper/config flags unless they target a
measured bucket.  The current best practical routes remain:

- graph-safe exact GDN/DeltaNet transaction/tape that can support stronger
  drafting without restore races;
- a genuinely stronger held-out drafter that clears the offline acceptance
  threshold;
- target-body kernel work with microbench evidence, especially GDN/linear
  attention or dense-model norm/full-attention buckets.
