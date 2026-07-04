# 2026-07-04 - Qwen27 Long-Context / Prompt-Processing Baseline

## Summary

Added a deterministic cold long-context retrieval suite and runner for the
current Qwen3.6 27B AutoRound webhie/BF16-scale INT8-LM-head recipe.

This is a **service / prompt-processing lane**, not a short-decode headline
record. Do not submit these rows as the main decode result. They are useful for
tracking TTFT, prompt-length behavior, context-capability, quality at longer
prompts, and later prompt-speed changes. Any service config promoted from this
lane must rerun the short realistic decode suite afterward to prove no decode
regression.

## Harness changes

- New suite:
  `repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json`.
- New runner:
  `experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh`.
- Shared harness:
  `scripts/bench-openai-long-context-suite.py`.

The first harness attempt only captured `delta.content`, so Qwen outputs routed
through OpenAI `delta.reasoning` appeared as empty text even though vLLM reported
completion tokens. The harness now:

- explicitly passes `{"chat_template_kwargs":{"enable_thinking":false}}`;
- captures both `delta.content` and `delta.reasoning`, matching the strict
  realistic-suite timing harness behavior;
- optionally requests vLLM stream `token_ids` (`LONG_RETURN_TOKEN_IDS=1` by
  default) so TTFT/decode timing does not depend on text chunking;
- records `cached_tokens` directly per row and requires all rows to be `0`;
- uses `LONG_MAX_TOKENS=128` by default because `64` truncated the JSON answer.

Important API detail: with the default `--reasoning-parser qwen3`, the
long-context JSON answers are emitted as reasoning deltas
(`content_delta_count=0`, `reasoning_delta_count=19-20`) even with thinking
disabled. The harness treats reasoning deltas as generated text for validation
and timing, as the strict decode harness already does.

For production-visible OpenAI `content`, set
`QWEN36_27B_REASONING_PARSER=` (empty). This no-parser mode was already
strict/fresh-valid at `64.932 tok/s` on the short decode suite, within the
current Qwen27 variance band of the approved `65.276 tok/s` row, and the
long-context content check below confirms it keeps exact retrieval while
streaming visible content.

## Early failures preserved

- `longctx1536-baseline`, `MAX_MODEL_LEN=2048`, `LONG_MAX_TOKENS=96`:
  failed HTTP 400 because the request was `1953 + 96 = 2049` tokens.
- `longctx1536-mtok64-baseline`, `MAX_MODEL_LEN=2048`, `LONG_MAX_TOKENS=64`:
  failed HTTP 400 because the request was `1985 + 64 = 2049` tokens.
- `longctx1024-baseline`, `MAX_MODEL_LEN=2048`, `LONG_MAX_TOKENS=64`:
  produced valid tokens with `cached_tokens=0`, but failed validation because
  the JSON was truncated before `arithmetic_result`.

These are not model-quality failures; they are runner/context-budget findings.

## Passing baselines

All rows below are cold, one request per prompt, unique prompt hashes,
`cached_tokens=0`, exact JSON retrieval fields passing.

### `MAX_MODEL_LEN=2048`, cases through target 1024

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx1024-mtok128-harnessfix-20260704T060501Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx1024-mtok128-harnessfix-20260704T060501Z`
- Rows: 2; prompt tokens `744`, `1455`.
- Summary: TTFT median `6.872s`, approximate prefill median `156.24 tok/s`,
  after-TTFT output median `38.17 tok/s`, wall median `8.38 tok/s`.

### `MAX_MODEL_LEN=4096`, cases through target 1536

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx1536-mml4096-baseline-20260704T060721Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx1536-mml4096-baseline-20260704T060721Z`
- Rows: 3; max actual prompt tokens `2268`.
- Summary: TTFT median `10.625s`, approximate prefill median
  `149.92 tok/s`, after-TTFT output median `38.57 tok/s`, wall median
  `6.10 tok/s`.

### `MAX_MODEL_LEN=8192`, cases through target 3072

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx3072-mml8192-baseline-20260704T061118Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx3072-mml8192-baseline-20260704T061118Z`
- Rows: 4; max actual prompt tokens `4296`.
- Summary: TTFT median `17.641s`, approximate prefill median
  `154.22 tok/s`, after-TTFT output median `56.86 tok/s`, wall median
  `4.15 tok/s`.

### `MAX_MODEL_LEN=16384`, cases through target 6144

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx6144-mml16384-baseline-20260704T061118Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx6144-mml16384-baseline-20260704T061118Z`
- Rows: 5; max actual prompt tokens `8795`.
- Summary: TTFT median `23.268s`, approximate prefill median
  `184.63 tok/s`, after-TTFT output median `66.76 tok/s`, wall median
  `2.94 tok/s`.

### `MAX_MODEL_LEN=32768`, cases through target 12288

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-baseline-20260704T061716Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-baseline-20260704T061716Z`
- Rows: 6; max actual prompt tokens `17706`.
- Server evidence: KV cache size `141,784` tokens, max concurrency `4.33x` at
  `32,768` tokens/request, graph capture `0.61 GiB`, init `120.74s` with
  `99.29s` compilation on first compile for the 4096 compile range.
- Summary: TTFT median `22.443s`, approximate prefill median
  `224.67 tok/s`, after-TTFT output median `60.19 tok/s`, wall median
  `3.08 tok/s`.

Per-row highlights from the 32K-cap run:

| case | actual prompt tokens | TTFT s | approx prefill tok/s | after-TTFT tok/s | wall tok/s |
|---|---:|---:|---:|---:|---:|
| `q27-lc-00512-early` | 744 | 25.445 | 29.24 | 39.65 | 2.68 |
| `q27-lc-01024-middle` | 1455 | 9.561 | 152.18 | 39.36 | 6.39 |
| `q27-lc-01536-late` | 2268 | 9.931 | 228.37 | 82.58 | 6.49 |
| `q27-lc-03072-middle` | 4296 | 19.441 | 220.98 | 77.30 | 3.49 |
| `q27-lc-06144-late` | 8795 | 35.419 | 248.31 | 63.68 | 1.97 |
| `q27-lc-12288-early` | 17706 | 65.973 | 268.38 | 56.71 | 1.11 |

The 512 row is a cold first request and includes one-time request/service
overhead, so use per-row and repeated-service comparisons when evaluating
prompt-speed changes. The approximate prefill metric is `prompt_tokens / TTFT`;
it is useful for relative service-lane comparisons but is not a pure kernel
prefill measurement.

### Production-visible no-parser content check

Same 32K-capability service lane, but with `QWEN36_27B_REASONING_PARSER=`:

- Result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-noparser-contentcheck-20260704T063156Z.json`
- Run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-noparser-contentcheck-20260704T063156Z`
- Rows: 6; max actual prompt tokens `17706`.
- Gate: exact JSON retrieval pass, `cached_tokens=0`, unique prompts.
- Output routing: every row streamed visible content deltas
  (`content_delta_count=19-20`, `reasoning_delta_count=0`).
- Summary: TTFT median `15.376s`, approximate prefill median
  `219.59 tok/s`, after-TTFT short-output median `61.71 tok/s`, wall median
  `4.96 tok/s`.

Recommendation: for production API behavior where clients read
`choices[].delta.content`, use the no-parser service variant. Keep it labeled
as the no-parser service variant and rerun the short strict decode suite if a
future change tries to replace the submitted `qwen3` parser headline recipe.

## Reproduction

Use the current validated decode recipe plus the long-context runner:

```bash
cd /home/steve/llm-optimizations

# 2K context, through the 1024 target case.
GPU_INDEX=1 PORT=19411 \
LABEL=qwen27-webhie-int8lmhead-bf16scale-longctx1024 \
MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 \
MAX_TARGET_PROMPT_TOKENS=1024 LONG_MAX_TOKENS=128 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh

# 32K context, through the 12288 target case.
GPU_INDEX=0 PORT=19410 \
LABEL=qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768 \
MAX_MODEL_LEN=32768 MAX_NUM_BATCHED_TOKENS=4096 \
MAX_TARGET_PROMPT_TOKENS=12288 LONG_MAX_TOKENS=128 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh

# 32K context with visible OpenAI content deltas.
GPU_INDEX=1 PORT=19411 \
LABEL=qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-noparser \
MAX_MODEL_LEN=32768 MAX_NUM_BATCHED_TOKENS=4096 \
MAX_TARGET_PROMPT_TOKENS=12288 LONG_MAX_TOKENS=128 \
QWEN36_27B_REASONING_PARSER= \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh
```

Default recipe baked into the runner:

- `MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`
- `QWEN36_27B_ENABLE_MTP=1`
- `NUM_SPECULATIVE_TOKENS=3`
- `QWEN36_27B_ENABLE_XPU_GRAPH=1`
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`
- `VLLM_XPU_LM_HEAD_INT8=1`
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`

## Next prompt-processing work

Latest MBT follow-up: `2026-07-04-long-context-mbt-screen.md`. Same-window 32K
no-parser service screening found `MAX_NUM_BATCHED_TOKENS=4096` remains the
best completed setting: MBT2048 passed but was slower (`22.330s` TTFT median,
`176.01` approx prefill tok/s), MBT4096 passed (`15.948s` TTFT median,
`207.91` approx prefill tok/s), and MBT8192 stalled on the final long request
with no complete gate artifact. Keep MBT4096 for this service lane.

1. Separate first-request cold service overhead from steady prompt processing
   with an explicit optional warmup request, while keeping promoted fresh rows
   cold and labeled.
2. Build a prompt-only or short-output micro-ladder for variance work; the
   current JSON retrieval output is useful for quality but adds decode noise.
3. Evaluate `MAX_NUM_BATCHED_TOKENS` for long prompts (`2048`, `4096`, `8192`)
   only as a service-lane setting, and always rerun the short strict decode
   suite afterward before adopting a service config.
4. If production clients need visible `content`, prefer the validated
   `QWEN36_27B_REASONING_PARSER=` service variant and rerun the short strict
   decode suite after any future parser/template change.
5. Calibrate the deterministic filler if future notes need target labels to
   match actual prompt tokens more closely; current results always record actual
   `usage.prompt_tokens`, which is the source of truth.
