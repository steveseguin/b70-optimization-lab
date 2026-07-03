# 2026-07-03 Post-cleanup control and fused top-1 plan

After archiving and reverting the no-win `CHUNKED_TOP1` / exact spec argmax
diagnostic code, the current Intel AutoRound + runtime INT8 LM-head recipe was
rerun as a same-day control.

## Post-cleanup control

Command shape:

```bash
LABEL=qwen27-intel-int8lmhead-postcleanup-control-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result JSON:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-intel-int8lmhead-postcleanup-control-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T163722Z.json`

Strict fresh gate:

- `realistic_final_gate.passed=true`;
- `cached_tokens=0` for all 12 prompts;
- median `62.33139790236203 tok/s`;
- p10 `57.893021197901405`;
- mean `62.78429215193106`;
- TTFT median `607.7865380211733 ms`.

Decision: valid support row, not a new record. The current record remains
`62.62792826965406 tok/s`. The post-cleanup result is close enough to confirm
that removing the no-win diagnostic code did not break the current recipe.

## Fused top-1 kernel plan

The current runtime INT8 LM-head prepares:

- `weight_t`: int8 `[5120, 248320]`;
- `weight_scale`: fp32 `[248320]`.

The current `get_top_tokens()` path still computes full logits through the
normal `lm_head.quant_method.apply()`, then reduces with `max()`. The failed
chunked diagnostic showed that multiple oneDNN GEMM calls plus Python
orchestration are slower than the full-logits path.

Do **not** wire another server path until a kernel-only screen wins.

Recommended bounded experiment:

1. Add a default-off XPU op such as
   `int8_lm_head_top1_out(hidden, weight_t, weight_scales, valid_vocab_size,
   vocab_start, top_ids, top_scores)`.
2. Fuse activation quantization inside the op; reusing
   `per_token_quant_int8_xpu` keeps an extra launch and `[M, 5120]` write/read.
3. Microbench `M={1,3,4,8}` against the current baseline:
   `per_token_quant_int8_xpu + int8_gemm_w8a8 + argmax`.
4. Only wire `LogitsProcessor.get_top_tokens()` behind a flag if the kernel
   microbench wins by at least a few percent on the real `[5120, 248320]`
   Qwen LM-head shape.

Risk: a naive scalar dot+argmax kernel is unlikely to beat oneDNN because it
still performs the full vocab-wide `5120 x 248320` INT8 dot work per row. A
real win likely needs DPAS/joint-matrix-style tiling and hidden-vector reuse,
or a deeper exact greedy verifier op that returns accept/replacement decisions
without materializing logits.
