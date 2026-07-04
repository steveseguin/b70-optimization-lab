# 2026-07-04 - Qwen27 current record reproduction support row

Status: **valid support row, not a new promoted record**.

This run reproduced the current Qwen27 best recipe after the draft-LM-head /
DFlash feasibility audit, before making any new source changes.

## Recipe

- Model: `webhie/Qwen3.6-27B-int4-AutoRound`
- Snapshot: `f5750c90b3776db658594df5fe8051098226dd8e`
- Runtime: local vLLM/XPU source stack already snapshotted in
  `2026-07-04-active-source-stack-checkpoint.md`
- GPU: one B70, `GPU_INDEX=0`
- Speculation: `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`
- XPU graph: `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`
- Runtime INT8 LM-head: `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`
- GDN state env:
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`
- Validity gate: fixed Qwen realistic suite, chat mode, each prompt once,
  `cached_tokens=0`, token-id timing for generated tokens 1-100 after TTFT.

## Result

Artifact:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-current-record-repro-20260704-codex-20260704T111830Z.json
```

Raw run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-current-record-repro-20260704-codex-20260704T111830Z
```

Metrics:

- strict gate: pass
- `cached_tokens_all_zero`: true
- median tok/s 1-100 after TTFT: `65.40973148473643`
- p10 tok/s 1-100 after TTFT: `58.292274675044496`
- mean tok/s 1-100 after TTFT: `64.10997285648747`
- median TTFT: `605.8498464990407 ms`
- rows: `12/12`, all `cached_tokens=0`

Server-side spec metrics during the run showed mean acceptance length around
`2.78-2.86`, with per-position acceptance roughly `0.80-0.84`,
`0.58-0.63`, `0.36-0.45`, consistent with the current record family.

## Decision

Do **not** submit this to LocalMaxxing. It is the same recipe as the approved
`65.27648650325429 tok/s` row (`cmr5iu3gk00bfq901nidgcana`) and the difference
is within the known same-window variance/inconclusive band for this recipe.

Use this as a live reproducibility support row: the current stack can still
reproduce the `~65 tok/s` strict fresh-response result, but no new optimization
has been proven.
