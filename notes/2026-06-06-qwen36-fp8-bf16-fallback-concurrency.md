# 2026-06-06 Qwen3.6 27B FP8 BF16-Fallback Diagnostic

Status update: rejected as a recommended serving lane. This note remains useful
for debugging XPU FP8 primitive failures and scheduler concurrency behavior, but
the active model direction is Qwen3.6 35B INT4 AutoRound or Gemma 12B+ INT4 /
proper FP8. The user explicitly does not want a BF16 fallback standing in for
FP8.

Goal: validate a Qwen OpenAI-compatible endpoint on the 4x B70 host and measure
about-2K-context decode throughput at increasing concurrency.

## Model

- Hugging Face ID: `vrfai/Qwen3.6-27B-FP8`
- Local path: `/mnt/fast-ai/llm-models/qwen3.6-27b-fp8-vrfai`
- Checkpoint file: one `model.safetensors`, about `34G`
- vLLM architecture: `Qwen3_5ForConditionalGeneration`
- Mode tested: text-only with `--language-model-only`
- Quantization config: `compressed-tensors`, tensor FP8 weights and tensor FP8
  input activations

The model includes vision config metadata, but all multimodal limits were zero
in this run, so vLLM served it as text-only.

## Native FP8 Failure

The direct compressed-tensors FP8 path did not reach serving on this host.

Failing launch shape:

```bash
/home/steve/.venvs/vllm-xpu/bin/vllm serve \
  /mnt/fast-ai/llm-models/qwen3.6-27b-fp8-vrfai \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen36-27b-fp8 \
  --trust-remote-code \
  --dtype auto \
  --quantization compressed-tensors \
  --language-model-only \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 32768 \
  --max-num-batched-tokens 2048 \
  --max-num-seqs 16 \
  --gpu-memory-utilization 0.90 \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching
```

Observed error during profiling:

```text
RuntimeError: could not set scales primitive attribute
torch.ops._xpu_C.fp8_gemm_w8a16(...)
```

The same error appeared with `--max-num-batched-tokens 8192` and `2048`, so this
was not only a scheduler-size issue. It is in the XPU FP8 linear GEMM path.

Raw logs:

- `/mnt/fast-ai/bench-results/qwen36-27b-fp8-vllm-serve/qwen36-27b-fp8-serve-c16-32k-20260606T193238Z.log`
- `/mnt/fast-ai/bench-results/qwen36-27b-fp8-vllm-serve/qwen36-27b-fp8-serve-c16-32k-mbt2048-20260606T193618Z.log`

## BF16 Fallback Patch

Added an opt-in local vLLM fallback:

```text
VLLM_XPU_FP8_LINEAR_BF16_FALLBACK=1
```

Patch:

```text
patches/vllm-xpu-qwen-fp8-bf16-fallback-20260606.patch
```

The fallback keeps the FP8 checkpoint values and stored scales, dequantizes each
linear weight tensor once after loading into BF16, then uses `F.linear`. This
avoids the failing Intel FP8 primitive, but it is not the requested operating
mode. Do not publish this as a Qwen FP8 or quality-equivalent production path.

Startup facts for the fallback at `max_model_len=4096`:

- model loading: `12.77 GiB` per worker
- available KV cache memory: `14.76 GiB`
- GPU KV cache size: `594,944` tokens
- vLLM max concurrency estimate for 4096 tokens/request: `145.25x`
- first compile/profile: about `78-95 s`, depending on profile cache

## Live Endpoint Shape Tested

Benchmark server shape:

```bash
VLLM_XPU_FP8_LINEAR_BF16_FALLBACK=1 \
/home/steve/.venvs/vllm-xpu/bin/vllm serve \
  /mnt/fast-ai/llm-models/qwen3.6-27b-fp8-vrfai \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen36-27b-fp8 \
  --trust-remote-code \
  --dtype auto \
  --quantization compressed-tensors \
  --language-model-only \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 4096 \
  --max-num-batched-tokens 4096 \
  --max-num-seqs 16  # then 32, then 64
```

The benchmark intentionally used a 4K server because the request asked for
about a 2K-context benchmark. This is not a 32K Qwen validation.

Smoke result:

```json
{
  "model": "qwen36-27b-fp8",
  "max_model_len": 4096,
  "completion_tokens": 13
}
```

## Benchmark Method

Script:

```text
scripts/bench-openai-concurrency.py
```

Shape:

- OpenAI-compatible `/v1/completions`
- stream enabled
- requested prompt tokens: `2048`
- observed prompt tokens: `2071`
- output tokens per request: `512`
- `temperature=0`
- `top_p=1.0`
- `ignore_eos=true`
- one warmup request before each run

Raw result files:

- `/mnt/fast-ai/bench-results/qwen36-27b-fp8-vllm-serve/qwen36-27b-fp8-concurrency-2k-512-20260606T194527Z.json`
- `/mnt/fast-ai/bench-results/qwen36-27b-fp8-vllm-serve/qwen36-27b-fp8-concurrency-2k-512-c16-c32-20260606T195102Z.json`
- `/mnt/fast-ai/bench-results/qwen36-27b-fp8-vllm-serve/qwen36-27b-fp8-concurrency-2k-512-c32-c64-20260606T195524Z.json`

## Results

Primary c1-c16 run:

| Concurrency | Aggregate output tok/s, wall | Aggregate output tok/s after first text | Mean per-request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `20.48` | `20.91` | `20.91` | `0.51 s` |
| 2 | `39.55` | `40.36` | `20.41` | `0.76 s` |
| 4 | `77.78` | `79.35` | `20.61` | `1.44 s` |
| 8 | `138.13` | `140.64` | `18.98` | `2.56 s` |
| 16 | `243.01` | `246.80` | `17.73` | `4.48 s` |

Focused c16-c32 run:

| Concurrency | Aggregate output tok/s, wall | Aggregate output tok/s after first text | Mean per-request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 16 | `237.21` | `240.88` | `17.30` | `4.63 s` |
| 32 | `402.51` | `407.90` | `16.21` | `8.21 s` |

Focused c32-c64 run:

| Concurrency | Aggregate output tok/s, wall | Aggregate output tok/s after first text | Mean per-request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 32 | `381.90` | `386.81` | `15.19` | `8.34 s` |
| 64 | `556.55` | `561.59` | `12.57` | `15.65 s` |

vLLM's 10-second logger showed higher steady decode windows after prefill:

- c16: about `250-330 tok/s`
- c32: about `490-640 tok/s`
- c64: still productive, but with a visible prefill/scheduler ramp

## Interpretation

For interactive use, c16 is the best latency/throughput balance in this fallback
profile. c32 is still practical if aggregate throughput matters more than TTFT.
c64 works mechanically and has the highest aggregate throughput, but the mean
TTFT is about `15.6 s` and requests visibly queue during the prefill ramp.

Rejected diagnostic Qwen text profile:

- `max_model_len=4096`
- `max_num_batched_tokens=4096`
- `max_num_seqs=32`
- `VLLM_XPU_FP8_LINEAR_BF16_FALLBACK=1`
- LAN endpoint through the standard no-auth frontdoor on `0.0.0.0:8000`

Do not compare these numbers directly to the older native-FP8 Qwen notes. Those
older runs reported much faster single-request decode, but the native XPU FP8
linear primitive failed here with this vLLM/driver/runtime combination. The
next model target is Qwen3.6 35B INT4 AutoRound using the XPU INT4 W4A16 path;
native block-FP8 work should continue separately and should not rely on this
BF16 fallback.
