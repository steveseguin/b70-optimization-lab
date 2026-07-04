# 2026-07-04 - Post-AWQ current record recipe repro support

Status: **valid strict fresh support row, not a new promoted record**.

After closing `cyankiwi/Qwen3.6-27B-AWQ-INT4` as a same-quality-class
checkpoint no-win, the approved webhie/BF16-scale current record recipe was
rerun through the strict candidate runner to confirm the active stack still
reproduces the record family.

## Recipe

- Model: `webhie/Qwen3.6-27B-int4-AutoRound`
- Snapshot: `f5750c90b3776db658594df5fe8051098226dd8e`
- Runtime: local vLLM/XPU stack; see the source snapshots linked from
  `2026-07-04-continuation-source-and-awq-state.md`
- GPU: one B70, `GPU_INDEX=0`
- Context: `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`,
  `MAX_NUM_SEQS=1`
- Speculation: `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`
- Graph: `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`
- Runtime INT8 LM-head: `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`
- GDN state env:
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`
- Validity: fixed Qwen realistic suite, chat mode, each prompt once,
  `cached_tokens=0`, token-id timing for generated tokens 1-100 after TTFT.

## Artifacts

Tracked compact artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-current-record-repro-post-awq-candidate-summary-20260704T140017Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-current-record-repro-post-awq-realistic128-chat-tokenids-qwensuite-20260704T140017Z.json
data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-webhie-bf16scale-current-record-repro-post-awq-20260704T140017Z.json
```

Raw run directory and server log:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-webhie-bf16scale-current-record-repro-post-awq-20260704T140017Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-webhie-bf16scale-current-record-repro-post-awq-20260704T140017Z/server.stdout.log
```

## Result

- smoke: pass (`{"answer": 42, "unit": "widgets"}`)
- strict realistic gate: pass
- rows: `12/12`
- `cached_tokens_all_zero`: true
- median tok/s 1-100 after TTFT: `66.12771533602819`
- p10 tok/s 1-100 after TTFT: `58.38213638742408`
- mean tok/s 1-100 after TTFT: `64.54120315866675`
- full-output after-TTFT median: `62.96806481876217 tok/s`
- wall-clock full-output median: `58.421063482113766 tok/s`
- median TTFT: `619.981024065055 ms`

No quality rerun was needed for this support note because the recipe and
checkpoint match the already quality-gated record packet. Do not promote this
as a new record without a matching quality rerun and variance review.

## Decision

Do **not** submit this to LocalMaxxing. It is the same recipe as the approved
`65.27648650325429 tok/s` row (`cmr5iu3gk00bfq901nidgcana`). The higher
`66.12771533602819 tok/s` median is useful live reproducibility evidence, but
the recipe is unchanged and the delta is inside the known practical variance
band for this lane.

This row confirms that after the AWQ no-win screen and runner fixes, the active
workspace still reproduces the webhie/BF16-scale record family. Continue with a
new mechanism only; do not repeat already closed config/checkpoint sweeps.
