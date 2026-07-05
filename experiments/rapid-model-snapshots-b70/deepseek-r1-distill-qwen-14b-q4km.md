# DeepSeek-R1-Distill-Qwen-14B Q4_K_M Diagnostic

Audience: future rapid-snapshot runs and anyone trying to benchmark reasoning
models through llama.cpp/OpenAI streaming on B70.

## Status

- Model: `bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF`
- Original model: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
- File: `DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf`
- HF revision: `9f5d77d401799416e0702290a691038b44012e0c`
- Local path:
  `/mnt/usb-models/llm-models/deepseek-r1-distill-qwen-14b-gguf/DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf`
- File size verified: `8988110240` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Result status: **diagnostic only, not promoted and not submitted to
  LocalMaxxing**.

## Why Not Promoted

The model served and generated tokens, but the default llama.cpp reasoning
parsing path emitted no streamable text or reasoning deltas for the 128-token
strict suite. `usage.completion_tokens=128` and `cached_tokens=0` were present,
but `chunk_count=0`, so the strict timing metric could not be measured.

Adding `--reasoning-format none` exposed the raw generated content and made the
strict token-timing gate pass, but every output began with visible `<think>` and
the 512-token manual/strict sanity checks still remained inside the reasoning
block without producing a final answer. That makes the measurable row raw
thinking-token throughput, not answer throughput for the realistic suite.

Because the current submission policy requires useful, non-misleading
fresh-response results, this lane is preserved as a diagnostic/template finding
instead of a promoted LocalMaxxing row.

## Evidence

Default parsing, invalid for timing:

- `data/rapid-model-snapshots-b70/deepseek-r1-distill-qwen-14b-q4km-llamacpp-faon-cacheoff-ctx4096-realistic128-20260705T001914Z.json`
- `data/rapid-model-snapshots-b70/deepseek-r1-distill-qwen-14b-q4km-llamacpp-faon-cacheoff-reasonon-ctx4096-realistic128-20260705T002048Z.json`

Both had `cached_tokens=0` on all prompts but `chunk_count=0` on all prompts.

Raw reasoning-format rows, measurable but not promoted:

| Label | Median tok/s 1-100 after TTFT | Notes |
| --- | ---: | --- |
| `reasonfmt-none-confirm-ctx4096-realistic128` | `35.28487506272765` | standalone confirmation, raw `<think>` tokens |
| `reasonfmt-none-ctx4096-realistic128` | `34.922277120721766` | standalone support, raw `<think>` tokens |
| `reasonfmt-none-confirm-ctx4096-realistic512` | `34.993287450215504` | 512-token sanity run; first 100 tokens similar, still reasoning-only in preview/manual check |
| `nothink-reasonfmt-none-ctx4096-realistic128` | `28.987335789078287` | concurrent four-GPU screen; `REASONING=off` still emitted `<think>` |
| `reasonfmt-none-ctx2048-realistic128` | `28.90644039544464` | concurrent four-GPU screen only, underreported |
| `reasonfmt-none-ub512-ctx4096-realistic128` | `28.8989098794776` | concurrent four-GPU screen only, underreported |
| `reasonfmt-none-poll100-ctx4096-realistic128` | `28.706437423359148` | concurrent four-GPU screen only, underreported |

Manual answer check:

- `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/manual/deepseek-r1-distill-qwen-14b-q4km-answer-check-20260705T003023Z/response.json`

The manual 512-token response had `has_end_think=false` and remained in the
reasoning trace, so it did not establish final-answer quality for the suite.

## Reproduce The Diagnostic

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/deepseek-r1-distill-qwen-14b-gguf/DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf \
MODEL_ALIAS=deepseek-r1-distill-qwen-14b-q4km \
LABEL=deepseek-r1-distill-qwen-14b-q4km-llamacpp-faon-cacheoff-reasonfmt-none-confirm-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19750 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=50 REASONING=auto \
EXTRA_LLAMA_ARGS='--cache-ram 0 --reasoning-format none' \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

Use this only as a raw reasoning-token diagnostic unless a future template or
prompting fix can produce final answers under the fixed realistic suite.

## Follow-Up Ideas

- Try a non-reasoning distilled checkpoint or a Qwen instruct model for a useful
  answer-throughput row.
- If this specific model matters, build a separate reasoning benchmark with a
  larger `max_tokens`, explicit accounting for thinking versus answer tokens,
  and a pass condition that verifies the answer section appears.
- Do not submit the `--reasoning-format none` rows as ordinary answer
  throughput.
