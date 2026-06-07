# 2026-06-06 Qwen 35B And Gemma 12B AutoRound Candidates

Goal: replace the rejected Qwen 27B BF16-fallback lane with a model candidate
that meets the current requirements:

- Qwen3.6 35B preferred.
- Gemma 12B or larger acceptable if faster or more stable.
- INT4 AutoRound or proper/native FP8 only.
- No BF16 fallback standing in for FP8.
- Prefix caching enabled.
- OpenAI-compatible LAN endpoint through the existing no-auth frontdoor.
- Target context no longer than `32768`.

## Candidate Order

1. `abhinand/Qwen3.6-35B-A3B-int4-AutoRound`
   - public and not gated from this host
   - about `22.13 GB`
   - `image-text-to-text`
   - W4A16 INT4 AutoRound
   - `quant_method=auto-round`
   - `packing_format=auto_round:auto_gptq`
   - `bits=4`, `group_size=128`, `sym=true`
   - local slot:
     `configs/model-slots/qwen36-35b-a3b-int4-autoround.env`

2. `Vishva007/gemma-4-12B-it-W4A16-AutoRound`
   - public and not gated from this host
   - about `7.81 GB`
   - Gemma 4 unified multimodal model
   - W4A16 INT4 AutoRound
   - `quant_method=auto-round`
   - `packing_format=auto_round:auto_gptq`
   - `bits=4`, `group_size=128`, `sym=true`
   - local slot:
     `configs/model-slots/gemma4-12b-it-int4-autoround.env`

   2026-06-06 result: downloaded but blocked. Local vLLM/Transformers does
   not recognize `model_type=gemma4_unified`.

3. `OPEA/gemma-3-12b-it-int4-AutoRound`
   - public and not gated from this host
   - about `8.0 GB`
   - Gemma 3 image+text model
   - 4-bit AutoRound/GPTQ-style weights
   - `quant_method=gptq`
   - `bits=4`, `group_size=128`, `sym=true`
   - local slot:
     `configs/model-slots/gemma3-12b-it-int4-autoround.env`

   2026-06-06 result: working. This is the fast Gemma lane today.

4. `Intel/Qwen3.6-35B-A3B-int4-mixed-AutoRound`
   - public and not gated from this host
   - about `21.52 GB`
   - W4A16 AutoRound, but with many more FP16 exclusions than the `abhinand`
     candidate
   - keep as a fallback if the preferred Qwen AutoRound checkpoint fails

5. `shieldstar/Qwen3.6-35B-A3B-int4-AutoRound-EC`
   - public and not gated from this host
   - about `20.93 GB`
   - extended-calibration AutoRound candidate
   - keep as a second Qwen fallback if the preferred checkpoint fails

## Rejected Or Blocked Paths

`Intel/Qwen3.6-35B-A3B-int4-AutoRound` is indexed publicly but returned `401`
from this host through the Hugging Face API and direct `hf download`, so it
requires auth or is otherwise not usable unauthenticated here.

`Qwen/Qwen3.6-35B-A3B-FP8` is public and popular, but it is a block-FP8
checkpoint. Local vLLM/XPU currently has no native 128x128 block-FP8 W8A8 GEMM
path. The available local options are:

- BF16 dequant fallback: rejected by user as the active direction.
- Block-FP8 requantization to per-channel FP8: quality-risking until evaluated.

`qwen36-27b-fp8-vrfai` is now marked `rejected-diagnostic` because the 2026-06-06
endpoint only worked after enabling `VLLM_XPU_FP8_LINEAR_BF16_FALLBACK=1`.

AWQ conversion variants are lower priority for B70/XPU. They often target
`awq_marlin` or CUDA-oriented paths, while local AutoRound `auto_round:auto_gptq`
maps to the XPU INC W4A16 path and Intel `int4_gemm_w4a16`.

Gemma 4 unified is blocked on local architecture support. The downloaded
`Vishva007/gemma-4-12B-it-W4A16-AutoRound` checkpoint advertises
`model_type=gemma4_unified`, which this local vLLM/Transformers stack rejects
before weight load. Do not recommend the profile until upstream support lands.

## Test Plan

1. Download the preferred Qwen AutoRound checkpoint to:
   `/mnt/fast-ai/llm-models/qwen3.6-35b-a3b-int4-autoround-abhinand`
2. Switch to:
   `scripts/switch-vllm-model-slot.sh switch qwen36-35b-a3b-int4-autoround`
3. Confirm `/v1/models` reports `max_model_len=32768`.
4. Confirm logs select the AutoRound/INC/XPU INT4 path, not FP8 BF16 fallback.
5. Run one text completion.
6. Run one image+text completion.
7. Benchmark about-2K prompt / 512 output at c1, c2, c4, and higher only if
   latency remains practical.
8. Restore `minimax-m27-c1` after testing unless another profile is explicitly
   promoted.

If Qwen fails to launch or is too slow, repeat the same ladder with
`gemma3-12b-it-int4-autoround`.

## Qwen 35B INT4 Result

Profile:

```bash
scripts/switch-vllm-model-slot.sh switch qwen36-35b-a3b-int4-autoround
```

Checkpoint:

```text
/mnt/fast-ai/llm-models/qwen3.6-35b-a3b-int4-autoround-abhinand
```

Local vLLM startup facts:

- architecture: `Qwen3_5MoeForConditionalGeneration`
- served name: `qwen36-35b-a3b-int4-autoround`
- context: `32768`
- prefix caching: enabled
- quantization: vLLM logged `quantization=inc`
- checkpoint quantization: `auto-round`, `auto_round:auto_gptq`, 4-bit,
  group size 128, symmetric
- image route: enabled with `--limit-mm-per-prompt '{"image":4}'`
- frontdoor default: injects `chat_template_kwargs={"enable_thinking":false}`
  so Qwen does not spend visible tokens on `<think>` output unless the client
  overrides it

Required local vLLM patch:

```text
patches/vllm-xpu-mamba-copy-pointer-uint64-20260606.patch
```

Why it was needed: before the patch, a 2K prompt crashed in
`vllm/v1/worker/mamba_utils.py` with `OverflowError: Python int too large to
convert to C long` while assigning XPU device pointer values into signed int64
Mamba copy buffers. The patch stores source and destination pointer metadata as
`torch.uint64`.

Smoke tests:

- Text chat worked through `0.0.0.0:8000`.
- A 1x1 red PNG image+text chat request returned `Red`.

About-2K prompt / 128-output decode benchmark through the no-auth frontdoor:

| Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s, wall | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `2071` | `128` | `17.28` | `7.41 s` |
| 2 | `2071` | `128` | `33.91` | `7.49 s` |
| 4 | `2071` | `128` | `61.54` | `8.21 s` |

Interpretation:

- Qwen 35B INT4 is functional and uses the desired INT4 path, not the rejected
  FP8 BF16 fallback.
- It is far slower than MiniMax for one user and slower than Gemma3 for
  concurrent text throughput.
- vLLM warned that no tuned XPU MoE config existed for
  `E=256,N=128,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16`.
  Building that tuned MoE config is the main obvious Qwen-specific optimization
  lead.
- The c4 synthetic benchmark had two normal `benchmark` continuations and two
  collapsed `!` continuations. Treat these numbers as throughput evidence, not
  a quality gate.

Raw files:

```text
/mnt/fast-ai/bench-results/qwen36-35b-int4-vllm-serve/qwen36-35b-int4-c1-2k-128-after-mamba-uint64-20260607T020923Z.json
/mnt/fast-ai/bench-results/qwen36-35b-int4-vllm-serve/qwen36-35b-int4-c2-c4-2k-128-after-mamba-uint64-20260607T021010Z.json
```

## Gemma 3 12B INT4 Result

Profile:

```bash
scripts/switch-vllm-model-slot.sh switch gemma3-12b-it-int4-autoround
```

Checkpoint:

```text
/mnt/fast-ai/llm-models/gemma3-12b-it-int4-autoround-opea
```

Local vLLM startup facts:

- architecture: `Gemma3ForConditionalGeneration`
- served name: `gemma3-12b-it-int4-autoround`
- context: `32768`
- prefix caching: enabled
- model load memory: about `2.54 GiB` per worker
- GPU KV cache: about `970,354` tokens
- theoretical full-32K concurrency from vLLM: about `29.61x`
- image route: enabled with `--limit-mm-per-prompt '{"image":4}'`

Important dtype nuance:

Gemma 3 rejected `float16` at launch:

```text
The model type 'gemma3' does not support float16. Reason: Numerical instability.
Please use bfloat16 or float32 instead.
```

The working profile therefore uses `VLLM_DTYPE=bfloat16`. This is not a BF16
weight fallback like the rejected Qwen FP8 path; the checkpoint remains an INT4
weight model. In practical terms, the Gemma3 slot is "INT4 weights with BF16
runtime activations".

Smoke tests:

- Text chat returned: `OK. I'm Gemma, a large language model from Google
  DeepMind.`
- A 1x1 red PNG image+text chat request returned `Red`.

Warmed about-2K prompt / 128-output decode benchmark through the no-auth
frontdoor:

| Concurrency | Prompt tokens each | Output tokens each | Aggregate output tok/s, wall | Mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `2072` | `128` | `31.31` | `4.09 s` |
| 2 | `2072` | `128` | `62.52` | `4.08 s` |
| 4 | `2072` | `128` | `124.48` | `4.09 s` |
| 8 | `2072` | `128` | `245.88` | `4.14 s` |
| 16 | `2072` | `128` | `166.14` | `9.31 s` |

Interpretation:

- Gemma3 12B INT4 is currently the fastest tested image+text slot.
- c8 is the practical live-concurrency setting for this profile.
- c16 does not improve throughput because the frontdoor/vLLM profile is built
  around 8 active generations; extra clients queue into later waves.
- The post-TTFT rate field from the benchmark script is not useful for this
  profile because vLLM/XPU coalesces stream chunks. Use wall-clock output rate.

Raw file:

```text
/mnt/fast-ai/bench-results/gemma3-12b-int4-vllm-serve/gemma3-12b-int4-concurrency-2k-128-warm-20260607T024447Z.json
```
