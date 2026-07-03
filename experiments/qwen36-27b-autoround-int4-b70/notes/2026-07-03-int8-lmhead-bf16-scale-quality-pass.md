# 2026-07-03: webhie INT8 LM-head BF16 scales quality pass

## Outcome

The current Qwen3.6 27B AutoRound lane has a small but validated fresh-response
record improvement:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- quantization label: `AutoRound INT4 W4A16 + runtime INT8 LM-head (BF16 scales)`
- runtime: local vLLM/XPU on one Intel Arc Pro B70, TP1, `qwen3_next_mtp`
  with `num_speculative_tokens=3`
- graph: `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`
- env delta: `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`
- strict fresh headline: **65.27648650325429 tok/s** median generated-token
  throughput for tokens 1-100 after TTFT
- p10/mean/TTFT: `59.608527188588106` / `65.07685647020962` /
  `603.5799405071884 ms`
- gate: Qwen realistic suite, chat mode, 12 unique prompts, each prompt once,
  `cached_tokens=0` on every request, `return_token_ids=true`
- quality: `pass_all=true`, `baseline_match_all=true`, repeat32 and 1K needle
  pass with `cached_tokens=0`

Promoted packet:

```text
results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json
```

LocalMaxxing payload:

```text
experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-20260703.queue.json
```

## Why This Was Tried

The synchronized timing run on the prior webhie INT8-LM-head recipe confirmed
that full logits / LM-head work still dominates the MTP3 path:

- `logits.local_argmax_lm_head`: `2322` calls, total `6013.69 ms`,
  average `2.5899 ms`
- `spec_decode.greedy_sample.compute_logits`: `1740` calls, total
  `4632.15 ms`, average `2.6622 ms`
- target `gpu_model_runner.compute_logits`: `580` calls, total `1579.82 ms`,
  average `2.7238 ms`
- proposer forward next: `1160` calls, total `771.95 ms`, average `0.6655 ms`

The earlier INT8 LM-head patch stores per-output-channel scales as FP32. The
new default-off option allows those scales to be stored as BF16:

```bash
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
```

This keeps the INT8 weight copy and INT8 activation quantization path intact,
but reduces the scale tensor bandwidth/format cost. It is not exact BF16
LM-head math; it is the same runtime INT8-LM-head quality lane with BF16 scale
storage, so it needs the same quality gate before promotion.

## Validation Rows

All rows below are strict fresh-response runs: fixed Qwen suite, each prompt
once, no prompt/KV/context/response reuse, no history acceleration, and
`cached_tokens=0` for every request.

| Row | Scale dtype | GPU | Median tok/s | p10 | Mean | TTFT med ms | Artifact |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| baseline reconfirm | FP32 | 0 | 64.4306959814215 | 59.74340472537171 | 63.920645238297965 | 604.7809924930334 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-reconfirm-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222251Z.json` |
| same-window control | FP32 | 2 | 64.23417302894208 | 59.35123023889924 | 63.588340391886085 | 605.1153619773686 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu2-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json` |
| same-window candidate | BF16 | 3 | 65.00467502982892 | 57.932897932484984 | 64.42610510957908 | 604.0464125107974 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu3-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json` |
| crossover candidate | BF16 | 2 | **65.27648650325429** | 59.608527188588106 | 65.07685647020962 | 603.5799405071884 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu2-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json` |
| crossover control | FP32 | 3 | 64.09039492601592 | 59.43825197781622 | 63.5105242613759 | 604.9520445521921 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu3-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json` |
| candidate repeat | BF16 | 3 | 64.86390312076414 | 59.32401527704932 | 64.84313630073925 | 605.4106915835291 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-repeat-gpu3-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T223150Z.json` |

The prior submitted webhie INT8-LM-head record is `64.30618876596424 tok/s`.
The three BF16-scale candidate rows are `65.276`, `65.005`, and `64.864 tok/s`;
the FP32-scale controls/reconfirm are `64.431`, `64.234`, and `64.090 tok/s`.
That is large enough to promote as an incremental record after the full quality
gate, but still small enough that future sub-1% source changes need paired
same-window/crossover handling before any claim.

## Quality Gate

Quality artifact:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-bf16scale-mtp3-cg8-repeat32-ctx1024-20260703T223138Z.json
```

Result:

- `pass_all=true`
- `baseline_match_all=true`
- repeat case passed
- long-context case passed
- long-context actual prompt tokens: `987`
- long-context cached tokens: `0`
- expected needle output: `B70_QWEN36_NEEDLE_20260609`

## Patch State

Before touching the local vLLM tree, the active dirty stack was saved at:

```text
patches/qwen36-27b-autoround-int4-b70/active-vllm-diff-before-lmhead-plan-20260703.patch
```

The active stack including this BF16-scale option is saved at:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-lmhead-bf16-scale-20260703.patch
```

SHA256:

```text
8f6d05d1bc97c3984c7cc1f96bfb017c8f63b29de4ac05dc741a9cd43e385ad0
```

The code change is default-off unless `VLLM_XPU_LM_HEAD_INT8=1` is already
enabled and `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16` is set.

## Next Source Work

This does not remove the main bottleneck; it only trims the current INT8
LM-head path. The larger remaining path is still a real fused verifier design:

- exact LM-head top-1 / candidate-vs-max without materializing full logits;
- compact verifier output rows;
- target verifier MoE/LM-head boundary reduction;
- avoid Python/chunked oneDNN top-1 paths, which were already no-win.

Do not continue random config sweeping on this row. Use the BF16-scale recipe as
the new control and require same-window/crossover checks for any claimed
sub-1% source-level improvement.
