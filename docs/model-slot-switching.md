# Single Model Slot Switching

This host should normally run one large model at a time. The public LAN API can
stay stable while the backend model changes.

Public endpoint:

```text
http://<server-lan-ip>:8000/v1
```

Backend slot:

```text
127.0.0.1:18080
```

The frontdoor is OpenAI-compatible and has no bearer-token requirement. It
limits concurrent generation requests according to the active model profile.

## Why One Slot

Four B70s can run a large model well, but two large vLLM backends at once would
fight for VRAM, compile cache, device handles, and port `8000`. The model-slot
setup makes the intended behavior explicit:

- stop the current backend;
- load exactly one selected profile;
- restart the same LAN frontdoor;
- keep clients pointed at the same base URL.

## Install Once

```bash
cd /home/steve/llm-optimizations
scripts/install-vllm-model-slot-service.sh --profile minimax-m27-c1
```

Install, enable at boot, and immediately move to the slot-managed MiniMax
profile:

```bash
cd /home/steve/llm-optimizations
scripts/install-vllm-model-slot-service.sh --profile minimax-m27-c1 --start
```

This installs:

```text
/etc/systemd/system/b70-vllm-slot.service
/etc/systemd/system/b70-openai-frontdoor.service
/etc/b70-vllm-slot/current.env
```

Tracked source files:

```text
deploy/systemd/b70-vllm-slot.service
deploy/systemd/b70-openai-frontdoor.service
configs/model-slots/*.env
scripts/serve-vllm-profile.sh
scripts/run-openai-frontdoor-profile.sh
scripts/switch-vllm-model-slot.sh
```

## Switch Models

List available profiles:

```bash
scripts/switch-vllm-model-slot.sh list
```

Switch back to the known-good MiniMax profile:

```bash
scripts/switch-vllm-model-slot.sh switch minimax-m27-c1
```

Try the preferred Qwen 35B INT4 AutoRound candidate after its weights are
present:

```bash
scripts/switch-vllm-model-slot.sh switch qwen36-35b-a3b-int4-autoround
```

Try the tested Gemma 3 12B INT4 AutoRound image+text candidate after its
weights are present:

```bash
scripts/switch-vllm-model-slot.sh switch gemma3-12b-it-int4-autoround
```

Try the current Gemma 4 12B INT4 AutoRound image+text candidate after the local
`gemma4_unified` vLLM backport is applied:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround
```

The switch command stops the generic slot services and the older
MiniMax-specific services before starting the selected slot. This avoids two
large models being loaded at the same time. It also disables the older
MiniMax-specific units when the generic slot is activated, so reboot behavior
stays single-model.

## Current Profiles

| Profile | Status | Modalities | Purpose |
| --- | --- | --- | --- |
| `minimax-m27-c1` | production | text | Current known-good MiniMax M2.7 INT4 AutoRound endpoint, 32K context, one active generation. |
| `qwen36-35b-a3b-int4-autoround` | research | text,image | Preferred Qwen 35B candidate. Public W4A16 AutoRound checkpoint, working after the local XPU Mamba pointer patch. |
| `gemma3-12b-it-int4-autoround` | research | text,image | Tested Gemma fallback. Public 12B INT4 AutoRound checkpoint, much faster than Qwen 35B on the 2K/128 concurrency ladder. |
| `gemma4-12b-it-int4-autoround` | research | text,image | Current Gemma 4 candidate. Intel W4A16 AutoRound checkpoint, working after Transformers `5.10.2` plus the local vLLM `gemma4_unified` backport. |
| `qwen36-27b-fp8-vrfai` | rejected-diagnostic | text | Do not use as a recommended lane. It only worked here with an opt-in BF16 dequant fallback for a failing XPU FP8 primitive. |
| `qwen36-35b-a3b-fp8` | blocked-native-xpu-fp8 | text,image | Official FP8 checkpoint is interesting, but the current local XPU path lacks native block-FP8 W8A8 support. |
| `qwen3-vl-30b-a3b-fp8` | blocked-native-xpu-fp8 | text,image | Multimodal FP8 candidate, blocked by the same native XPU block-FP8 concern until proven otherwise. |

## Check Status

```bash
scripts/switch-vllm-model-slot.sh status
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/v1/models
```

The frontdoor status includes the active profile metadata:

```json
{
  "model_slot": {
    "name": "minimax-m27-c1",
    "modalities": "text",
    "status": "production"
  },
  "frontdoor": {
    "auth": "none",
    "max_active_generations": 1
  }
}
```

## Validation Gate For A New Profile

Do not call a new profile production-ready until it passes:

1. `/v1/models` reports the expected model and context length.
2. A text completion returns valid tokens.
3. For VL profiles, `/v1/chat/completions` accepts a real image request.
4. Short decode throughput is measured after warmup.
5. 16K and 32K prompt TTFT are measured.
6. c2/c4 concurrency tests report both throughput and latency.
7. Quality smoke tests pass with the same sampling settings used for service.

## Notes On The Candidate Models

`qwen36-35b-a3b-int4-autoround` is the current first-choice Qwen profile. The
checkpoint is `abhinand/Qwen3.6-35B-A3B-int4-AutoRound`, a public W4A16
AutoRound model with `quant_method=auto-round` and
`packing_format=auto_round:auto_gptq`. In local vLLM, that AutoRound format
maps to the INC XPU W4A16 path and Intel `int4_gemm_w4a16`, which is the
quality-preserving hardware path we want to test. Qwen 35B also needed the
local vLLM patch in
`patches/vllm-xpu-mamba-copy-pointer-uint64-20260606.patch`; without it, a
2K prompt crashed in `vllm/v1/worker/mamba_utils.py` with `OverflowError:
Python int too large to convert to C long` while copying Mamba cache pointers.

`gemma3-12b-it-int4-autoround` is the tested fast Gemma fallback. The
checkpoint is `OPEA/gemma-3-12b-it-int4-AutoRound`, a Gemma 3 image+text model
with 4-bit AutoRound/GPTQ-style weights. vLLM rejects Gemma 3 with `float16`
for numerical-stability reasons, so the profile uses `bfloat16` as the
runtime activation dtype while keeping INT4 weights. That is not the same as
the rejected Qwen FP8 BF16-dequant fallback.

`gemma4-12b-it-int4-autoround` is now the current Gemma 4 image+text candidate.
The checkpoint is `Intel/gemma-4-12B-it-int4-AutoRound`, a W4A16 AutoRound
model with `model_type=gemma4_unified`. It needed Transformers `5.10.2` and
the local vLLM backport in
`patches/vllm-gemma4-unified-backport-b70-20260607.patch`. The active profile
uses `bfloat16` as the 16-bit activation dtype while the weights remain the
INT4 AutoRound checkpoint. The validated c16 profile keeps the same no-auth
LAN endpoint on `0.0.0.0:8000`, supports text and image requests, and reports
`max_model_len=32768`.

Avoid treating the Qwen FP8 profiles as production candidates right now. On
2026-06-06, the native compressed-tensors FP8 path failed during profiling on
this host with `RuntimeError: could not set scales primitive attribute` in
`torch.ops._xpu_C.fp8_gemm_w8a16`. The local BF16 fallback patch avoids that
crash by dequantizing FP8 weights into BF16 and using `F.linear`, but the user
explicitly rejected BF16 fallback as the active model direction. The block-FP8
Qwen 35B family also needs native XPU 128x128 block-FP8 W8A8 GEMM support;
the local alternatives are BF16 dequant fallback or requantized FP8, neither
of which should be promoted as quality-equivalent without a separate eval.

The rejected Qwen 27B BF16-fallback diagnostic used `max_model_len=4096`, about
`2071` prompt tokens per request, and `512` generated tokens:

| Concurrency | Aggregate output tok/s, wall | Mean request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: |
| 1 | `20.48` | `20.91` | `0.51 s` |
| 16 | `243.01` | `17.73` | `4.48 s` |
| 32 | `402.51` | `16.21` | `8.21 s` |
| 64 | `556.55` | `12.57` | `15.65 s` |

Those numbers are useful as a scheduler/concurrency diagnostic only. Full
details are in `notes/2026-06-06-qwen36-fp8-bf16-fallback-concurrency.md`.

## 2026-06-06 INT4 AutoRound Results

These are text decode throughput measurements through the no-auth LAN
frontdoor at about 2K prompt tokens and 128 generated tokens per request.
Use `aggregate output tok/s, wall` as the primary number; XPU/vLLM sometimes
coalesces stream chunks, so the post-TTFT derived field can be misleading.

Qwen 35B INT4 AutoRound, after applying the Mamba pointer `uint64` patch:

| Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s, wall | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `2071` | `128` | `17.28` | `7.41 s` |
| 2 | `2071` | `128` | `33.91` | `7.49 s` |
| 4 | `2071` | `128` | `61.54` | `8.21 s` |

Qwen notes:

- `/v1/chat/completions` text worked after the frontdoor injected
  `chat_template_kwargs={"enable_thinking":false}` by default.
- A 1x1 red PNG image+text request returned `Red`.
- Prefix caching was enabled.
- vLLM logged `quantization=inc`, consistent with the XPU INT4 W4A16 path.
- vLLM also warned that no tuned MoE config existed for
  `E=256,N=128,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16`.
  That likely leaves performance on the table.

Gemma 3 12B INT4 AutoRound:

| Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s, wall | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `2072` | `128` | `31.31` | `4.09 s` |
| 2 | `2072` | `128` | `62.52` | `4.08 s` |
| 4 | `2072` | `128` | `124.48` | `4.09 s` |
| 8 | `2072` | `128` | `245.88` | `4.14 s` |
| 16 | `2072` | `128` | `166.14` | `9.31 s` |

Gemma notes:

- Text smoke returned: `OK. I'm Gemma, a large language model from Google
  DeepMind.`
- A 1x1 red PNG image+text request returned `Red`.
- vLLM reported `max_model_len=32768`, prefix caching enabled, and about
  `970,354` GPU KV-cache tokens, or about `29.61x` theoretical concurrency for
  full 32K requests.
- c8 is the practical live-concurrency profile from the warmed 2K/128 run.
  c16 mostly queues behind the configured 8 live sequences and reduces total
  wall throughput.

Raw local result files:

```text
/mnt/fast-ai/bench-results/qwen36-35b-int4-vllm-serve/qwen36-35b-int4-c1-2k-128-after-mamba-uint64-20260607T020923Z.json
/mnt/fast-ai/bench-results/qwen36-35b-int4-vllm-serve/qwen36-35b-int4-c2-c4-2k-128-after-mamba-uint64-20260607T021010Z.json
/mnt/fast-ai/bench-results/gemma3-12b-int4-vllm-serve/gemma3-12b-int4-concurrency-2k-128-warm-20260607T024447Z.json
```

## 2026-06-07 Gemma 4 INT4 AutoRound Results

Gemma 4 12B INT4 AutoRound:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround
```

Model:

```text
Intel/gemma-4-12B-it-int4-AutoRound
```

Local path:

```text
/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel
```

Serving facts:

- served name: `gemma4-12b-it-int4-autoround`
- endpoint: `http://0.0.0.0:8000/v1`
- auth: none
- backend: vLLM/XPU
- tensor parallel: `4`
- runtime dtype: `bfloat16`
- quantization path reported by vLLM: `inc`
- max model length: `32768`
- max live generations/frontdoor: `16`
- prefix caching: enabled
- multimodal limit: `--limit-mm-per-prompt '{"image":4}'`

Text and image smoke tests passed after the final restart. Text returned
`OK`; a base64 PNG image request returned `Blue`.

Benchmark shape:

- prompt requested: `2048` tokens
- actual prompt tokens: about `2071` per request
- generated tokens: `512` per request
- forced decode: `ignore_eos=true`
- benchmark path:
  `scripts/bench-openai-concurrency.py`

| Concurrency | Aggregate decode tok/s after first text | Aggregate output tok/s, wall | Mean request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `58.22` | `30.39` | `58.22` | `8.05 s` |
| 2 | `117.27` | `59.70` | `58.89` | `8.44 s` |
| 4 | `236.10` | `116.33` | `59.71` | `9.00 s` |
| 8 | `467.76` | `217.39` | `59.63` | `10.20 s` |
| 16 | `922.18` | `396.11` | `59.60` | `11.97 s` |

Important notes:

- The useful decode number is the after-first-text output-token rate. It shows
  about `58-60 tok/s` per active request.
- Wall aggregate includes the 2K prefill and TTFT. At c16, wall aggregate was
  about `396 output tok/s`.
- vLLM reported `GPU KV cache size: 1,004,337 tokens`, or `30.65x` theoretical
  concurrency for 32K requests. Only c16 has been validated.
- Do not set `--limit-mm-per-prompt '{"image":4,"video":0,"audio":0}'`; that
  failed during Gemma4 unified dummy multimodal profiling. Keep
  `--limit-mm-per-prompt '{"image":4}'`.

Raw local result files:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/concurrency-2k-512-c1-c2-c4-c8-20260607T034622Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/concurrency-2k-512-c16-20260607T035019Z.json
```

Full reproduction notes:

```text
../experiments/gemma4-12b-int4-autoround-vllm/README.md
```
