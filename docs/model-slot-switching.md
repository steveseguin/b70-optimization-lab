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

Try the full-32K Gemma 4 profile with 8 active generations:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
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
| `gemma4-12b-it-int4-autoround-c8` | production | text,image | Active full-context Gemma 4 profile: 32768-token context, 8 active generations, prefix caching, XPU graph capture, no-auth LAN endpoint. |
| `gemma4-12b-it-int4-autoround-c64` | research-c64 | text,image | High-concurrency Gemma 4 profile: 64 active generations, prefix caching, 4480-token context selected to fit 64 full contexts in VRAM. |
| `gemma4-12b-it-int4-autoround-c8-gmem096` | rejected-startup-memory | text,image | Same as c8 but `gpu_memory_utilization=0.96`; rejected after engine startup failure near the VRAM boundary. |
| `gemma4-12b-it-int4-autoround-c8-gmem097` | rejected-startup-memory | text,image | Same as c8 but `gpu_memory_utilization=0.97`; rejected because startup free VRAM was below requested utilization. |
| `gemma4-12b-it-int4-autoround-c8-cs1-8` | rejected-device-lost | text,image | Same as c8 but `compile_sizes=[1,8]`; rejected after IGC fallback compile and `UR_RESULT_ERROR_DEVICE_LOST` during repeat validation. |
| `gemma4-12b-it-int4-autoround-c8-xpugraph-mbt2048` | rejected-device-lost | text,image | Same as c8 graph but `max_num_batched_tokens=2048`; gained KV headroom but hit `UR_RESULT_ERROR_DEVICE_LOST` during canary/sampling. |
| `gemma4-12b-it-int4-autoround-c8-nolog` | experiment-nolog | text,image | Same as c8 but frontdoor event logging disabled; quality matched but no clear throughput win. |
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

`gemma4-12b-it-int4-autoround-c64` is the high-concurrency variant for many
shorter live sessions. It uses the same model and endpoint, but sets
`max_num_seqs=64`, `FRONTDOOR_MAX_ACTIVE_GENERATIONS=64`, keeps prefix caching
enabled, and lowers `max_model_len` to `4480`. This was selected empirically:
vLLM reported `292317` GPU KV tokens and `65.25x` full-context concurrency at
`4480`, while `4864` only reached `60.15x`. Do not derive the c64 context by
dividing the c16 KV budget; the c64 scheduler/compile profile changes the
available KV budget.

`gemma4-12b-it-int4-autoround-c8` is the active production full-context variant
selected after the c64 tradeoff became too short. It uses the same Gemma 4 INT4 AutoRound
checkpoint and same no-auth LAN endpoint, but keeps `max_model_len=32768` and
caps vLLM/frontdoor live generations at `8`. After the 2026-06-07 XPU graph
promotion, startup reported `1,004,909` GPU KV-cache tokens and `30.67x`
theoretical full-32K concurrency, so the c8 cap is conservative. The profile
passed an 8-way near-limit probe with `32703` prompt tokens and one output token
per request. For normal generation, leave output headroom below 32768 total
prompt+generated tokens.

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

## 2026-06-07 Gemma 4 C64 Profile

Switch command:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c64
```

Serving facts:

- endpoint: `http://0.0.0.0:8000/v1`
- auth: none
- model: `Intel/gemma-4-12B-it-int4-AutoRound`
- served name: `gemma4-12b-it-int4-autoround`
- max model length: `4480`
- max active generations: `64`
- prefix caching: enabled
- vLLM full-context concurrency: `65.25x`

Context search:

| Max model len | GPU KV tokens | vLLM full-context concurrency | Outcome |
| ---: | ---: | ---: | --- |
| `15616` | `667253` | `42.73x` | too high |
| `10368` | `507081` | `48.91x` | too high |
| `7680` | `405664` | `52.82x` | too high |
| `4864` | `292589` | `60.15x` | too high |
| `4096` | `291995` | `71.29x` | fits |
| `4480` | `292317` | `65.25x` | selected |

Short-prompt c64 TTFT with about `123` prompt tokens and one generated token:

| Mean TTFT | p50 TTFT | p95 TTFT | Max TTFT |
| ---: | ---: | ---: | ---: |
| `0.882 s` | `0.712 s` | `1.139 s` | `1.140 s` |

Short-prompt c64 output run with about `123` prompt tokens and `128` generated
tokens per request:

| Concurrency | Aggregate output tok/s, wall |
| ---: | ---: |
| `64` | `1614.41` |

Near-limit prompt smoke:

| Actual prompt tokens | Output tokens | TTFT |
| ---: | ---: | ---: |
| `4323` | `1` | `0.631 s` |

Raw local result files:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-ttft-100p-1o-20260607T062129Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-decode-100p-128o-20260607T062143Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c64-4480-longprompt-4300p-1o-20260607T062228Z.json
```

## 2026-06-07 Gemma 4 C8 Production Full-Context Profile

Switch command:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

Serving facts:

- endpoint: `http://0.0.0.0:8000/v1`
- auth: none
- model: `Intel/gemma-4-12B-it-int4-AutoRound`
- served name: `gemma4-12b-it-int4-autoround`
- max model length: `32768`
- max active generations: `8`
- prefix caching: enabled
- XPU graph capture: enabled
- vLLM full-context concurrency estimate: `30.67x`
- GPU KV cache size: `1004909` tokens

Short-prompt c8 TTFT with about `119` prompt tokens and one generated token:

| Mean TTFT | Max TTFT |
| ---: | ---: |
| `0.151 s` | `0.183 s` |

Short-prompt c8 output run with about `119` prompt tokens and `128` generated
tokens per request:

| Profile | Concurrency | Aggregate output tok/s, wall |
| --- | ---: | ---: |
| pre-graph c8 | `8` | `247.49` |
| XPU graph c8, promoted mean of 3 | `8` | `703.59` |

The XPU graph promotion matched the saved quality canary hashes before it was
copied into the canonical production profile. It keeps the same model,
quantization, context length, concurrency cap, and prefix caching; it changes
only the compile/graph execution path:

```bash
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
```

Post-promotion startup facts:

```text
torch.compile took 4.12 s
Graph capturing finished in 4 s
init engine took 19.05 s
GPU KV cache size: 1,004,909 tokens
Maximum concurrency for 32,768 tokens per request: 30.67x
```

Sustained decode checks on the promoted graph profile:

| Shape | Concurrency | Wall aggregate output tok/s |
| --- | ---: | ---: |
| `119` prompt tokens, `256` output tokens | `8` | `796.18` |
| `119` prompt tokens, `512` output tokens | `8` | `780.97` |
| `119` prompt tokens, `1024` output tokens | `8` | `731.12` |

512-output scaling on the same production endpoint:

| Concurrency | Wall aggregate output tok/s |
| ---: | ---: |
| `1` | `112.77` |
| `2` | `205.47` |
| `4` | `398.98` |
| `8` | `784.69` |

Near-full-context probes:

| Shape | Prompt tokens each | Output tokens each | Mean TTFT | Max TTFT | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `c8` cold-ish long prefill | `30690` | `1` | `22.17 s` | `39.03 s` | Before the repeated prefix was warm. |
| `c8` prefix-cache-warm near limit | `32703` | `1` | `1.94 s` | `3.22 s` | Reused most of the prior repeated prefix. |

Over-limit canary:

```text
32894 input tokens + 1 output token was rejected, correctly, because it exceeds 32768 total tokens.
```

Raw local result files:

```text
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-100p-1o-fastprompt-20260607T065104Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-100p-128o-fastprompt-20260607T065116Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-8x32000p-1o-20260607T064822Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/c8-32768-8x32703p-1o-20260607T065041Z.json
/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround/prod-c8-xpugraph-promoted-20260607T080322Z
```

Repo summary:

```text
../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-b70-c8-32768.json
```
