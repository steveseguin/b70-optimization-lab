# Gemma 4 12B IT INT4 AutoRound On B70 vLLM/XPU

This folder tracks the Gemma 4 bring-up on the 4x Intel Arc Pro B70 host.

Goal:

- run `Intel/gemma-4-12B-it-int4-AutoRound`;
- keep the public endpoint OpenAI-compatible on `0.0.0.0:8000`;
- support text and image requests;
- keep a 32K context window, with the current c8 profile limiting live
  generations to 8 while keeping full 32K context;
- characterize the shorter c64 profile needed for 64 active clients;
- measure single-user and concurrent decode behavior;
- keep the setup reproducible for another Ubuntu 24.04 B70 system.

## Current Status

Status on 2026-06-07: c8 is the active production profile. It now uses XPU
graph capture after matching the quality canary and improving warmed c8
short-decode throughput. c16 and c64 remain documented alternate profiles.

The endpoint is running through the generic model-slot services:

```text
Public endpoint: http://<server-lan-ip>:8000/v1
Auth: none
Served model name: gemma4-12b-it-int4-autoround
Backend: vLLM/XPU on 127.0.0.1:18080
Production c8 profile: 32768 context, 8 live generations
Default high-context c16 profile: 32768 context, 16 live generations
High-concurrency c64 profile: 4480 context, 64 live generations
Modalities tested: text, image
```

Text smoke after the final restart returned exactly `OK`.
A real base64 PNG image request returned `Blue`.

## Model

Hugging Face:

```text
https://huggingface.co/Intel/gemma-4-12B-it-int4-AutoRound
```

The Intel model card describes this as a W4A16 AutoRound quantization of
`google/gemma-4-12B-it`, with group size `128` and symmetric quantization. The
local vLLM startup logs report `quantization=inc`, which means the checkpoint is
using the Intel AutoRound/INC INT4 path rather than the rejected FP8/BF16
fallback direction.

Local model path:

```text
/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel
```

Downloaded footprint on this host is about `7.3G`.

## Why It Needed Patching

The original local stack had Transformers `5.7.0`, which did not recognize
`model_type=gemma4_unified`. The fix was:

1. Upgrade the serving venv to Transformers `5.10.2`.
2. Backport vLLM's `gemma4_unified.py` model implementation.
3. Register `Gemma4UnifiedForConditionalGeneration` in vLLM's model registry.
4. Add the missing `gemma4_mm.py` helper used by the unified implementation.

Patch snapshot:

```text
../../patches/vllm-gemma4-unified-backport-b70-20260607.patch
```

Validation commands used after patching:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/model_executor/models/gemma4_mm.py \
  /home/steve/src/vllm/vllm/model_executor/models/gemma4_unified.py \
  /home/steve/src/vllm/vllm/model_executor/models/registry.py

/home/steve/.venvs/vllm-xpu/bin/python - <<'PY'
from transformers import AutoConfig, AutoProcessor
from vllm.model_executor.models.registry import ModelRegistry
model = "/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel"
cfg = AutoConfig.from_pretrained(model, trust_remote_code=True)
proc = AutoProcessor.from_pretrained(model, trust_remote_code=True)
print(type(cfg).__name__, cfg.model_type, cfg.architectures)
print(type(proc).__name__)
print(ModelRegistry.resolve_model_cls(cfg.architectures)[0].__name__)
PY
```

Expected output includes:

```text
Gemma4UnifiedConfig gemma4_unified ['Gemma4UnifiedForConditionalGeneration']
Gemma4UnifiedProcessor
Gemma4UnifiedForConditionalGeneration
```

## Slot Profile

Base c16 profile:

```text
../../configs/model-slots/gemma4-12b-it-int4-autoround.env
```

Key settings:

```bash
MODEL_SLOT_HF_ID="Intel/gemma-4-12B-it-int4-AutoRound"
MODEL_DIR=/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel
VLLM_DTYPE=bfloat16
VLLM_QUANTIZATION=auto
VLLM_TENSOR_PARALLEL_SIZE=4
VLLM_MAX_MODEL_LEN=32768
VLLM_MAX_NUM_BATCHED_TOKENS=4096
VLLM_MAX_NUM_SEQS=16
VLLM_ENABLE_PREFIX_CACHING=1
VLLM_EXTRA_ARGS=(--limit-mm-per-prompt '{"image":4}')
FRONTDOOR_HOST=0.0.0.0
FRONTDOOR_PORT=8000
FRONTDOOR_MAX_ACTIVE_GENERATIONS=16
```

High-concurrency profile:

```text
../../configs/model-slots/gemma4-12b-it-int4-autoround-c64.env
```

Key c64 settings:

```bash
VLLM_MAX_MODEL_LEN=4480
VLLM_MAX_NUM_BATCHED_TOKENS=4096
VLLM_MAX_NUM_SEQS=64
VLLM_ENABLE_PREFIX_CACHING=1
FRONTDOOR_MAX_ACTIVE_GENERATIONS=64
```

Active production c8 profile:

```text
../../configs/model-slots/gemma4-12b-it-int4-autoround-c8.env
```

Key c8 settings:

```bash
VLLM_MAX_MODEL_LEN=32768
VLLM_MAX_NUM_BATCHED_TOKENS=4096
VLLM_MAX_NUM_SEQS=8
VLLM_ENABLE_PREFIX_CACHING=1
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
FRONTDOOR_MAX_ACTIVE_GENERATIONS=8
```

`VLLM_DTYPE=bfloat16` is the 16-bit activation/runtime dtype. The weights remain
the INT4 AutoRound checkpoint; this is not the rejected Qwen FP8 BF16-dequant
fallback.

## Start Or Switch To This Model

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround
```

Switch to the 64-active-client profile:

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c64
```

Switch to the full-32K, 8-active-generation profile:

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

Check status:

```bash
curl -fsS http://127.0.0.1:8000/status
curl -fsS http://127.0.0.1:8000/v1/models
```

Expected `/v1/models` includes:

```json
{
  "id": "gemma4-12b-it-int4-autoround",
  "max_model_len": 32768
}
```

The c64 profile reports `max_model_len=4480`.

## Smoke Tests

Text:

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"gemma4-12b-it-int4-autoround",
    "messages":[{"role":"user","content":"Reply with exactly: OK"}],
    "max_tokens":8,
    "temperature":0
  }'
```

Image requests use the normal OpenAI `image_url` content shape. The validated
smoke used a base64 PNG data URL and asked for the dominant color.

## Benchmark Shape

The useful benchmark run used forced generation with `ignore_eos=true`:

```bash
cd /home/steve/llm-optimizations
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-openai-concurrency.py \
  --base-url http://127.0.0.1:8000 \
  --tokenizer /mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel \
  --prompt-tokens 2048 \
  --output-tokens 512 \
  --concurrency 1 \
  --concurrency 2 \
  --concurrency 4 \
  --concurrency 8 \
  --warmups 1 \
  --timeout 1800 \
  --output-json /mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/concurrency-2k-512-c1-c2-c4-c8-20260607T034622Z.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-openai-concurrency.py \
  --base-url http://127.0.0.1:8000 \
  --tokenizer /mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel \
  --prompt-tokens 2048 \
  --output-tokens 512 \
  --concurrency 16 \
  --warmups 1 \
  --timeout 1800 \
  --output-json /mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/concurrency-2k-512-c16-20260607T035019Z.json
```

The earlier `single-2k-512` file is not a valid decode-rate measurement because
it allowed early EOS and the model stopped after only a few generated tokens.

## Results

Prompt tokens were about `2071` per request. Each request generated `512`
tokens. Decode rates below are output-token rates after first streamed text,
which isolates generation from the long 2K prefill/TTFT portion. Wall aggregate
is also included because it is what a user feels for full prompt+decode runs.

| Concurrency | Aggregate decode tok/s after first text | Aggregate output tok/s wall | Mean per-request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `58.22` | `30.39` | `58.22` | `8.05 s` |
| 2 | `117.27` | `59.70` | `58.89` | `8.44 s` |
| 4 | `236.10` | `116.33` | `59.71` | `9.00 s` |
| 8 | `467.76` | `217.39` | `59.63` | `10.20 s` |
| 16 | `922.18` | `396.11` | `59.60` | `11.97 s` |

Interpretation:

- Single stream decode is about `58-60 tok/s`.
- Per-request decode stays close to `60 tok/s` through `c16`.
- Aggregate warmed decode scales almost linearly to `c16`, reaching about
  `922 tok/s` after TTFT.
- The 2K prefill path is the current latency cost; wall throughput at `c16` was
  about `396 output tok/s`.

## C64 Profile

The 64-active-client profile cannot keep the 32K context window. The important
finding is that changing `max_num_seqs` from `16` to `64` changes vLLM's profiled
KV budget and compile shape. Do not estimate c64 context by dividing the c16
`1,004,337` KV-token budget by 64.

Search results:

| Max model len | GPU KV tokens | vLLM full-context concurrency | Outcome |
| ---: | ---: | ---: | --- |
| `15616` | `667253` | `42.73x` | too high for 64 full contexts |
| `10368` | `507081` | `48.91x` | too high for 64 full contexts |
| `7680` | `405664` | `52.82x` | too high for 64 full contexts |
| `4864` | `292589` | `60.15x` | too high for 64 full contexts |
| `4096` | `291995` | `71.29x` | fits, but leaves more headroom |
| `4480` | `292317` | `65.25x` | selected c64 profile |

Selected c64 profile:

```text
max_model_len=4480
max_num_seqs=64
max_active_generations=64
prefix caching enabled
```

The selected profile uses `4480 * 64 = 286720` logical KV tokens against a
profiled `292317` token KV budget. That is close to full without crossing the
full-64 admission boundary.

Short-prompt one-token TTFT probe:

| Concurrency | Prompt tokens each | Output tokens each | Mean TTFT | p50 TTFT | p95 TTFT | Max TTFT |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `64` | `123` | `1` | `0.882 s` | `0.712 s` | `1.139 s` | `1.140 s` |

Short-prompt 128-token output run:

| Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s wall | Mean TTFT field |
| ---: | ---: | ---: | ---: | ---: |
| `64` | `123` | `128` | `1614.41` | `5.04 s` |

For the 128-token run, use the wall aggregate as the useful throughput number.
The post-first-text decode field is not reliable for this short-prompt shape
because vLLM/XPU coalesces streamed output chunks.

Near-limit prompt smoke:

| Requested prompt | Actual prompt tokens | Output tokens | TTFT |
| ---: | ---: | ---: | ---: |
| `4300` | `4323` | `1` | `0.631 s` |

Raw files:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-ttft-100p-1o-20260607T062129Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-decode-100p-128o-20260607T062143Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-longprompt-4300p-1o-20260607T062228Z.json
```

## C8 Full-Context Profile

The active production Gemma 4 profile keeps `max_model_len=32768` and
caps live requests at 8. This keeps the LAN endpoint useful for full-context
clients without dropping to the c64 profile's shorter 4480-token window.

Selected c8 profile:

```text
max_model_len=32768
max_num_seqs=8
max_active_generations=8
prefix caching enabled
XPU graph capture enabled
```

Current production startup with XPU graph capture reported:

```text
torch.compile took 4.12 s on cached graph restart
Graph capturing finished in 4 s
init engine took 19.05 s
Available KV cache memory: 27.48 GiB
GPU KV cache size: 1,004,909 tokens
Maximum concurrency for 32,768 tokens per request: 30.67x
```

The `30.67x` line is vLLM's KV-capacity estimate. The service is intentionally
capped at 8 live generations because the goal for this profile is predictable
LAN behavior with full 32K context, not maximum theoretical admission.

Short-prompt one-token TTFT probe after rebuilding the benchmark prompt
generator:

| Concurrency | Prompt tokens each | Output tokens each | Mean TTFT | Max TTFT |
| ---: | ---: | ---: | ---: | ---: |
| `8` | `119` | `1` | `0.151 s` | `0.183 s` |

Short-prompt 128-token output run:

| Profile | Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s wall | Mean TTFT field |
| --- | ---: | ---: | ---: | ---: | ---: |
| pre-graph c8 | `8` | `119` | `128` | `247.49` | `4.12 s` |
| XPU graph c8 promoted mean | `8` | `119` | `128` | `703.59` | `1.46 s` |

For the 128-token run, use the wall aggregate as the useful throughput number.
The post-first-text decode field is not reliable for this short-prompt shape
because vLLM/XPU coalesces streamed output chunks.

Near-full-context probes:

| Shape | Prompt tokens each | Output tokens each | Mean TTFT | Max TTFT | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `c8` cold-ish long prefill | `30690` | `1` | `22.17 s` | `39.03 s` | Useful long-prefill signal before the repeated prefix was warm. |
| `c8` prefix-cache-warm near limit | `32703` | `1` | `1.94 s` | `3.22 s` | Reused most of the earlier repeated 30.7K-token prefix. |

Over-limit canary:

```text
requested target 34300 -> 32894 input tokens per c8 lane
requested output tokens: 1
result: rejected as expected
reason: 32894 + 1 exceeds the 32768 max context window
```

This is the right behavior. For one output token, the prompt must stay at or
below `32767` input tokens. For normal generation, leave more room for output.

Raw files:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-100p-1o-fastprompt-20260607T065104Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-100p-128o-fastprompt-20260607T065116Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-8x32000p-1o-20260607T064822Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-8x32703p-1o-20260607T065041Z.json
```

Repo summary:

```text
results-20260607-b70-c8-32768.json
```

## Production C8 Baseline

After promoting c8 to production metadata, the same profile was restarted and
revalidated. Cached restart loaded AOT compile in `4.91 s`, initialized the
engine in `17.88 s`, and reported `1,004,337` GPU KV tokens, or `30.65x`
theoretical full-32K concurrency.

Quality canary:

```text
exact_ok: OK
copy_phrase: satin cobalt orbit
small_arithmetic: 7
red_image: Red
```

Sequential production benchmark baseline:

| Shape | Prompt tokens each | Output tokens each | Concurrency | Primary result |
| --- | ---: | ---: | ---: | ---: |
| short TTFT | `119` | `1` | `8` | mean TTFT `0.106 s` |
| short decode | `119` | `128` | `8` | wall aggregate `250.21 tok/s` |
| long prefill | `30690` | `1` | `8` | mean TTFT `22.21 s` |

Repo summary:

```text
results-20260607-production-c8-baseline.json
```

## XPU Graph Promotion

On 2026-06-07, the c8 production profile was updated to enable XPU graph
capture with communication ops. This keeps the same model, INT4 AutoRound
weights, `bfloat16` activation dtype, `32768` context, c8 concurrency cap, and
prefix caching. It changes only the compile/graph execution path.

Validated settings:

```bash
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
```

Post-promotion startup on the canonical production slot reported:

```text
torch.compile took 4.12 s in total
GPU KV cache size: 1,004,909 tokens
Maximum concurrency for 32,768 tokens per request: 30.67x
Graph capturing finished in 4 s
init engine took 19.05 s
```

Quality gate:

```text
expected outputs: pass
baseline text/hash comparison: pass
text checks: OK, satin cobalt orbit, 7
image check: Red
```

Repeated production c8 short-decode checks after promotion:

| Run | Prompt tokens each | Output tokens each | Concurrency | Mean TTFT | Wall aggregate output tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `119` | `128` | `8` | `1.658 s` | `613.72` |
| 2 | `119` | `128` | `8` | `1.354 s` | `751.58` |
| 3 | `119` | `128` | `8` | `1.365 s` | `745.48` |
| mean | `119` | `128` | `8` | `1.459 s` | `703.59` |

This is the current best production profile. The earlier non-graph c8
production baseline was about `240-250 tok/s` for the same short-decode shape.
The graph branch also ran a longer validation loop before promotion:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/xpugraph-validation-20260607T075901Z
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-promoted-20260607T080322Z
```

The 32K prefill leg did not materially improve with XPU graph. It stayed around
`22.28 s` mean TTFT for eight concurrent `30690`-token prompts with one output
token. Treat the win as a decode-path improvement, not a long-prefill fix.

Sustained decode characterization on the promoted production c8 graph profile:

| Shape | Prompt tokens each | Output tokens each | Concurrency | Mean TTFT | Wall aggregate output tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| repeat mean | `119` | `256` | `8` | `2.530 s` | `796.18` |
| repeat mean | `119` | `512` | `8` | `2.542 s` | `780.97` |
| repeat mean | `119` | `1024` | `8` | `2.519 s` | `731.12` |

512-token scaling on the same production endpoint:

| Concurrency | Prompt tokens each | Output tokens each | Mean TTFT | Wall aggregate output tok/s |
| ---: | ---: | ---: | ---: | ---: |
| `1` | `119` | `512` | `2.190 s` | `112.77` |
| `2` | `119` | `512` | `2.415 s` | `205.47` |
| `4` | `119` | `512` | `2.500 s` | `398.98` |
| `8` | `119` | `512` | `2.526 s` | `784.69` |

Raw result directories:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-256o-repeat-20260607T084540Z
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-512o-repeat-20260607T084633Z
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-1024o-repeat-20260607T084718Z
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-scaling-512o-20260607T084806Z
```

LocalMaxxing submissions:

| Shape | tok/s | ID |
| --- | ---: | --- |
| c8, 119 prompt, 256 output, repeat mean | `796.18` | `cmq3jm75g000tlj01bx4frdf0` |
| c8, 119 prompt, 512 output, repeat mean | `780.97` | `cmq3jm7cx000wlj01wm75wqmk` |

Rejected same-day branches:

| Branch | Result |
| --- | --- |
| `gemma4-12b-it-int4-autoround-c8-mbt8192` | Quality matched, but c8 short decode fell to about `245.75 tok/s`, short TTFT worsened, and GPU KV dropped to `730,379` tokens. |
| `gemma4-12b-it-int4-autoround-c8-mbt2048` | Quality matched and GPU KV rose to `1,201,507` tokens, but c8 short decode fell to about `235.37 tok/s`. |
| `gemma4-12b-it-int4-autoround-c8-gmem097` | Rejected at startup. Free memory on `xpu:0` was about `30.61/31.89 GiB`, below the `0.97` utilization request of about `30.93 GiB`. |
| `gemma4-12b-it-int4-autoround-c8-gmem096` | Rejected at startup/engine init near the same memory boundary. Keep production at `VLLM_GPU_MEMORY_UTILIZATION=0.95`. |
| `gemma4-12b-it-int4-autoround-c8-cs1-8` | Rejected. First compile had six `ocloc`/IGC `error code 245` fallbacks and `torch.compile` took `315.80 s`; cached repeat validation later hit `UR_RESULT_ERROR_DEVICE_LOST` during sampling. |
| `gemma4-12b-it-int4-autoround-c8-xpugraph-mbt2048` | Rejected. It raised GPU KV to `1,201,940` tokens and `36.68x` theoretical 32K concurrency, but first compile took `214.55 s` and it hit `UR_RESULT_ERROR_DEVICE_LOST` during the canary/sampling path. |
| `gemma4-12b-it-int4-autoround-c8-nolog` | Quality matched, but no clear win. c8 short decode was `714.81 tok/s`, within the promoted graph profile's normal variance, while one-token TTFT worsened. |

Those branches are kept as reproducible profiles for future tuning, but they are
not the active production path.

## Startup Observations

Known-good c16 startup reported:

```text
Resolved architecture: Gemma4UnifiedForConditionalGeneration
quantization=inc
max_seq_len=32768
enable_prefix_caching=True
max_num_batched_tokens=4096
max_num_seqs=16
Loading weights took 0.73 s
torch.compile took 4.66 s in total on cached restart
GPU KV cache size: 1,004,337 tokens
Maximum concurrency for 32,768 tokens per request: 30.65x
```

The `30.65x` line is a theoretical KV-capacity statement, not a claim that
`c30` has been benchmarked. The validated profile is `c16`.

Known-good c64 startup reported:

```text
max_seq_len=4480
enable_prefix_caching=True
max_num_batched_tokens=4096
max_num_seqs=64
torch.compile took 67.31 s on first launch for this shape
GPU KV cache size: 292,317 tokens
Maximum concurrency for 4,480 tokens per request: 65.25x
```

Each tried max-context value created a new torch.compile cache key and took
about 66-67 seconds on first launch. Cached restarts should be faster, but c64
has a real first-start operational cost.

Current production c8 startup with XPU graph reported:

```text
max_seq_len=32768
enable_prefix_caching=True
max_num_batched_tokens=4096
max_num_seqs=8
torch.compile took 4.12 s on cached graph restart
Graph capturing finished in 4 s
init engine took 19.05 s
GPU KV cache size: 1,004,909 tokens
Maximum concurrency for 32,768 tokens per request: 30.67x
```

## Known Bad Setting

Do not set this:

```bash
VLLM_EXTRA_ARGS=(--limit-mm-per-prompt '{"image":4,"video":0,"audio":0}')
```

That launch failed during Gemma4 unified dummy multimodal profiling:

```text
ValueError: Found 1 <|image|> tokens in the text but no images were passed.
RuntimeError: Engine core initialization failed.
```

The working setting is:

```bash
VLLM_EXTRA_ARGS=(--limit-mm-per-prompt '{"image":4}')
```

vLLM still logs a multimodal warmup warning and profiles a video-sized encoder
cache budget, but real image requests work.

## Next Work

- Measure 16K and 32K prompt TTFT for c1/c4/c8/c16.
- Compare c64 at 4480 against c16 at 32768 for real chat traffic, not just
  synthetic short prompts.
- Revisit vLLM's Gemma4 unified dummy multimodal profiling so image-only limits
  do not accidentally trip video/audio warmup behavior.
- Submit a minimal upstream vLLM issue or PR once the backport is narrowed to
  the registry/helper delta needed by this release branch.
