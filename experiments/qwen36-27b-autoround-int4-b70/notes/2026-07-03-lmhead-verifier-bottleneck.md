# 2026-07-03 Qwen27 AutoRound LM-head / verifier bottleneck

This note records the post-GGUF diagnostics on the current valid
`Intel/Qwen3.6-27B-int4-AutoRound` recipe:

- one B70, TP1, vLLM/XPU, chat endpoint;
- XPU graph on, `qwen3_next_mtp`, `num_speculative_tokens=3`;
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`.

The current headline remains the conservative strict/fresh row in
`results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`
at `53.522 tok/s` median for generated tokens 1-100 after TTFT, with
`cached_tokens=0` on all prompts and LocalMaxxing id
`cmr4gokx90061nv01lhoe3ft8`.

## Diagnostic 1: promoted row-copy trace

Command shape:

```bash
LABEL=intel-mtp3-cg8-promotesource-statecopytrace-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_GDN_STATE_COPY_TRACE_FILE=/home/steve/llm-optimizations/data/qwen36-27b-autoround-int4-b70-baselines/gdn-state-copy-trace-promotesource-mtp3-cg8-20260703.jsonl \
VLLM_XPU_GDN_STATE_COPY_TRACE_MAX_LINES=20000 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result:

- strict fresh gate passed, `cached_tokens=0`;
- result JSON:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-statecopytrace-realistic128-chat-tokenids-qwensuite-20260703T110115Z.json`;
- median `53.315903500324566 tok/s`, p10 `48.19289917408962`, mean
  `54.556953290541465`, TTFT median `531.6374224494211 ms`;
- the trace file was not created / had zero records.

Interpretation: the promoted recipe is no longer exercising the
`_xpu_gdn_copy_state_rows_native` / `_xpu_gdn_promote_running_state_native`
row-copy helper that the earlier accepted-state trace made suspicious. The
source-slot promotion plus disabled accepted-state postprocess appears to have
removed that physical promoted-copy hot path for this recipe. Do not continue
blind GDN row-copy tuning as the next optimization target unless a new trace
shows the helper is active again.

## Diagnostic 2: synchronized decode timing

Command shape:

```bash
LABEL=intel-mtp3-cg8-promotesource-timing-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_DECODE_TIMING=1 \
VLLM_XPU_DECODE_TIMING_SYNC=1 \
VLLM_XPU_DECODE_TIMING_LABEL_REGEX='gpu_model_runner\.compute_logits|gpu_model_runner\.rejection_sampler|spec_decode\.greedy_sample|spec_decode\.propose\.(model_forward|build_attn_metadata|copy_buffers|select_hidden|select_sample_hidden|tree_compute_logits)' \
VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX='gpu_model_runner\.compute_logits|gpu_model_runner\.rejection_sampler|spec_decode\.greedy_sample|spec_decode\.propose\.(model_forward|tree_compute_logits)' \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result:

- strict fresh gate passed, `cached_tokens=0`;
- result JSON:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-timing-realistic128-chat-tokenids-qwensuite-20260703T110403Z.json`;
- median `48.7760300301037 tok/s`, p10 `44.08489836567844`, mean
  `49.72035406731854`, TTFT median `546.0799699649215 ms`;
- throughput is diagnostic only because synchronized timing perturbs the run.

Timing summary from the server log:

| label | count | total ms | avg ms |
| --- | ---: | ---: | ---: |
| `spec_decode.greedy_sample_total` | 1740 | 8056.550848 | 4.630202 |
| `spec_decode.greedy_sample.compute_logits` | 1740 | 7746.011826 | 4.451731 |
| `gpu_model_runner.compute_logits` | 580 | 2565.828298 | 4.423842 |
| `spec_decode.propose.model_forward_next` | 1160 | 754.523739 | 0.650451 |
| `spec_decode.propose.model_forward_first` | 580 | 481.404285 | 0.830007 |
| `gpu_model_runner.rejection_sampler` | 568 | 250.345809 | 0.440750 |
| `spec_decode.greedy_sample.argmax` | 1740 | 157.589345 | 0.090569 |
| `spec_decode.propose.copy_buffers_next` | 1160 | 35.497580 | 0.030601 |

Interpretation: logits / LM-head work dominates the current promoted MTP3 path.
The draft proposer model forward itself is sub-ms; the expensive part is the
full LM-head/logits path used for draft-token selection and target verification.
Metadata, hidden-state selection, and buffer copy regions are small in this
profile.

## Next source target

The next bounded source experiments should focus on exact greedy verifier /
LM-head cost, not GDN copy:

1. Add a default-off exact greedy spec path that uses precomputed target argmax
   ids plus target bonus argmax ids instead of passing full logits through the
   normal sampler. This must preserve exact target replacement on first mismatch
   and target-owned bonus token on full accept; the existing draft-only shortcut
   is invalid for headline use because it does not do that.
2. Test proposer-side `use_local_argmax_reduction` / `get_top_tokens` only as
   a small bounded screen. On TP1 it probably still computes the full LM-head,
   so expectations should be modest.
3. The larger win probably requires an AutoRound/INC W4A16 LM-head top-1 or
   candidate-vs-max kernel that avoids materializing full vocab logits for
   greedy verification. This is deeper kernel work, but the timing profile says
   it is the real hot path.

Any promoted result still needs the Qwen realistic suite, one cold response per
prompt, `cached_tokens=0`, returned token IDs, and the quality suite before
LocalMaxxing submission.
