# Gemma 4 12B IT INT4 AutoRound On B70 vLLM/XPU

This folder tracks the Gemma 4 bring-up on the 4x Intel Arc Pro B70 host.

Goal:

- run `Intel/gemma-4-12B-it-int4-AutoRound`;
- keep the public endpoint OpenAI-compatible on `0.0.0.0:8000`;
- support text and image requests;
- keep a 32K context window;
- measure single-user and concurrent decode behavior;
- keep the setup reproducible for another Ubuntu 24.04 B70 system.

## Current Status

Status on 2026-06-07: working research profile.

The endpoint is running through the generic model-slot services:

```text
Public endpoint: http://<server-lan-ip>:8000/v1
Auth: none
Served model name: gemma4-12b-it-int4-autoround
Backend: vLLM/XPU on 127.0.0.1:18080
Context: 32768
Max live generations: 16
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

Active profile:

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

`VLLM_DTYPE=bfloat16` is the 16-bit activation/runtime dtype. The weights remain
the INT4 AutoRound checkpoint; this is not the rejected Qwen FP8 BF16-dequant
fallback.

## Start Or Switch To This Model

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround
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
- Compare c16 against c24/c30 only if users need many simultaneous 32K
  sessions.
- Revisit vLLM's Gemma4 unified dummy multimodal profiling so image-only limits
  do not accidentally trip video/audio warmup behavior.
- Submit a minimal upstream vLLM issue or PR once the backport is narrowed to
  the registry/helper delta needed by this release branch.
