# Gemma 4 26B A4B Model And Runtime Options

Research snapshot: 2026-06-23.

## Primary Model Identity

- Target model: `gemma-4-26B-A4B-it`.
- Architecture facts from Google/Unsloth cards: about 25.2B total parameters,
  about 3.8B active parameters, MoE, text plus image support, long context.
- More specific public model-card facts: 30 layers, sliding window 1024,
  256K-token context, 262K vocabulary, 128 total experts with 8 active experts
  plus 1 shared expert, and text+image modalities.
- User quality rule for this lane: Q8 / INT8-or-better by default. Do not make
  INT4 AutoRound, Q4_K, IQ4, or MXFP4 the default optimization path.

## Unsloth GGUF Assets

Primary repo:

```text
unsloth/gemma-4-26B-A4B-it-GGUF
revision 3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a
```

Important files from Hugging Face metadata:

| File | Bytes | Use |
| --- | ---: | --- |
| `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` | `27,636,230,944` | Primary no-quality-loss Q8 target/verifier lane. Use this for promoted Gemma 26B B70 records unless the user explicitly accepts a different quantization. |
| `gemma-4-26B-A4B-it-Q8_0.gguf` | `26,859,859,744` | Alternate Q8_0 control lane only. It is smaller and can be useful for compatibility/perf diagnosis, but it is not a promoted replacement for `UD-Q8_K_XL` under the no-quality-loss constraint. |
| `gemma-4-26B-A4B-it-UD-Q6_K_XL.gguf` | `23,295,389,472` | Lower-quality side experiment only if Q8 cannot fit useful context. |
| `gemma-4-26B-A4B-it-MXFP4_MOE.gguf` | `16,551,046,944` | Public-speed comparison only; not quality-equivalent to the Q8 target. |
| `mtp-gemma-4-26B-A4B-it.gguf` | `461,766,816` | Draft/MTP follow-up after no-spec baseline. |
| `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf` | local | Current promoted default MTP draft for the `UD-Q8_K_XL` target/verifier lane. Under the current VDR2 strict identity it remains faster than Q4_K_M/Q5_K_M/Q6_K/Q8_0 draft swaps. |
| `MTP/gemma-4-26B-A4B-it-Q4_K_M-MTP.gguf` | local | Strict VDR2 screen on 2026-06-27 passed validity but lost (`84.232 tok/s` median 1-100). Do not use as default. |
| `MTP/gemma-4-26B-A4B-it-Q5_K_M-MTP.gguf` | local | Strict VDR2 screen on 2026-06-27 passed validity but lost (`88.110 tok/s`), below the current Q4_0-draft record (`117.915 tok/s`; also below the then-current `98.340 tok/s` row). |
| `MTP/gemma-4-26B-A4B-it-Q6_K-MTP.gguf` | local | Strict VDR2 screen on 2026-06-27 passed validity but lost (`85.729 tok/s`), below the current Q4_0-draft record. |
| `MTP/gemma-4-26B-A4B-it-Q8_0-MTP.gguf` | `461,766,816` | Alternate official Unsloth MTP draft file. Current strict VDR2 screen passed validity but lost (`88.245 tok/s`), below the current Q4_0-draft record. |
| `MTP/gemma-4-26B-A4B-it-F16-MTP.gguf` | `855,228,576` | Higher-precision draft head. Tested 2026-06-23; valid but much slower than Q8_0 draft. |
| `MTP/gemma-4-26B-A4B-it-BF16-MTP.gguf` | `855,228,576` | Higher-precision draft head. Tested 2026-06-23; valid but much slower than Q8_0 draft. |
| `mmproj-F16.gguf` | `1,193,058,784` | Optional multimodal smoke after text baseline; not required for speed work. |

The download script is pinned to the repo revision above and validates the exact
primary Q8 file size. Override `FILENAME` and `EXPECTED_BYTES` explicitly for
MTP or mmproj downloads.

Draft/assistant alternatives:

- `google/gemma-4-26B-A4B-it-assistant` exists as a Hugging Face checkpoint and
  is the official assistant/draft-family reference.
- `AtomicChat/gemma-4-26B-A4B-it-assistant-GGUF` exposes assistant GGUF files
  including `gemma-4-26B-A4B-it-assistant.Q8_0.gguf` at `461,767,072` bytes.
  Do not use this with stock upstream llama.cpp: it uses fork metadata
  `general.architecture = gemma4_assistant` and `mtp.*` tensor names, while
  upstream `c926ad098` expects Unsloth-style `gemma4-assistant` and `nextn.*`
  metadata. The stock loader fails with `unknown model architecture:
  'gemma4_assistant'`. It belongs to AtomicChat's custom
  `atomic-llama-cpp-turboquant` / `--mtp-head` path unless a conversion is done
  on a copy.

Different-model side lane:

- `DiffusionGemma` is based on the Gemma 4 26B MoE architecture and is marketed
  for low-latency/high-speed small-batch generation, but it is a different
  generation method and not the same `gemma-4-26B-A4B-it` checkpoint. Treat it
  as a future side lane if the Q8 causal model cannot meet speed targets.

Lower-precision public-speed lanes:

- QAT/W4A16, NVFP4, MXFP4, Q4_K, and IQ-family GGUFs are useful for public
  context, memory controls, or future side lanes, but not for the default Q8
  result packet. vLLM explicitly warns that the 26B-A4B MoE expert dimension is
  sensitive to 4-bit quantization; the vLLM fallback should be int8
  per-channel weight-only, not W4A16.
- QAT GGUF side lane started 2026-06-24 after the Q8 MTP path plateaued in the
  mid-90s and before the later `103.299 tok/s` pre-final-gate Q8-target
  selected-softmax/weighted-sum direct-unroll/q-only record. The candidate repo is
  `unsloth/gemma-4-26B-A4B-it-qat-GGUF`, with local target path
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-qat-gguf/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf`
  and draft path
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-qat-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`.
  Treat this as a **quality-labeled side lane**, not the Q8/INT8 headline:
  QAT is trained for 4-bit robustness, but it is still not the same quality
  promise as Q8 target/verifier. Do not submit it as the Q8 lane unless a
  separate quality decision explicitly promotes it.

## Runtime Options

### llama.cpp SYCL / GGUF

This is the primary lane. It matches the one-replica-per-GPU goal and avoids
tensor-parallel PCIe collectives. The local build is:

```text
/home/steve/src/llama.cpp
commit dec5ca557
build /home/steve/src/llama.cpp/build-sycl-b70
```

Important local facts:

- `llama-server` needs oneAPI environment libraries; source
  `/opt/intel/oneapi/setvars.sh --force` or use the repo launcher.
- The launcher maps a filtered `ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>` to
  `-dev SYCL0`, which is correct for one process per visible device.
- Default `GGML_SYCL_DISABLE_OPT=1` is intentional because llama.cpp issue
  `#21893` reports Gemma 4 nonsense output on B70 with optimized SYCL paths.
- The built server exposes MTP/speculation flags:
  `--spec-draft-model`, `--spec-type draft-mtp`, `--spec-draft-n-max`,
  `--spec-draft-device`, and `--spec-draft-ngl`.
- External llama.cpp MTP issue traffic includes reports of speculative/MTP
  regressions and sensitivity to draft quality. For this lane, keep the
  official Q8-class Gemma MTP draft as the default. Treat draft KV compression
  (`--spec-draft-type-k/v q8_0`) as a measured cache/runtime experiment only:
  promote it only if it passes the fixed realistic suite and beats the current
  primary metric under the same gate.

### vLLM/XPU Int8 Per-Channel

This is the second lane, not the first. vLLM's Gemma 4 recipe recommends
`--quantization int8_per_channel_weight_only` for 26B A4B because its smaller
MoE expert dimensions are sensitive to 4-bit quantization. Use this if llama.cpp
Q8 is too slow, lacks a needed feature, or fails multimodal support.

Do not use one `--data-parallel-size 4` process for this model on vLLM/XPU yet.
There is a public Gemma 4 MoE DP issue whose workaround is separate DP=1
instances. That also matches this lane's no-PCIe-overhead design.

### Ollama

Useful as a compatibility/control runtime for GGUF and chat template behavior.
Not the first optimization runtime because low-level SYCL flags, per-run
identity, and LocalMaxxing-style reproducibility are harder to preserve.

### Vulkan / Community B70 Kits

There is a community B70 repository claiming SYCL is generally stronger for
dense Gemma/Qwen decode while Vulkan can be relevant for some MoE speculative
paths. Treat this as an idea source only. This lane starts with the local SYCL
build because it gives the best direct control over B70 flags and matches prior
repo practices.

## LocalMaxxing Reference

Use LocalMaxxing for public target context, not as direct Q8 comparison. Current
public top rows include lower-precision modes such as MXFP4/Q4, which are
outside the default quality lane. Search/title snippets on 2026-06-23 showed
the Google model page around `87.3 tok/s`, the Unsloth GGUF page around
`94.3 tok/s`, and a Gemopus GGUF fine-tune around `94.5 tok/s`; these are mixed
public rows rather than a B70 Q8 target.

Submission requirements and the lane-specific payload shape are in
[localmaxxing-and-targets.md](localmaxxing-and-targets.md). Submit only after
this repo has a valid realistic-suite record packet: model file/revision,
runtime commit, GPU count, fixed prompt-suite identity, all `cached_tokens=0`,
primary median tok/s for generated tokens 1-100 after TTFT, p10/mean/TTFT/wall
and full-512 metrics, prompt and output hashes, quality status, throughput
JSON, server log path, env/flags, and reproducible command.

## Source Links

- Unsloth GGUF repo:
  <https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF>
- Google Gemma 4 MTP overview:
  <https://ai.google.dev/gemma/docs/mtp/overview>
- vLLM Gemma 4 recipe:
  <https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html>
- vLLM Gemma 4 MoE DP issue:
  <https://github.com/vllm-project/vllm/issues/38999>
- llama.cpp B70/Gemma 4 corruption report:
  <https://github.com/ggml-org/llama.cpp/issues/21893>
- llama.cpp Gemma/MTP regression tracker:
  <https://github.com/ggml-org/llama.cpp/issues/24266>
- LocalMaxxing model page:
  <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>
- LocalMaxxing API docs:
  <https://www.localmaxxing.com/en/api-docs>
- DiffusionGemma overview:
  <https://ai.google.dev/gemma/docs/diffusiongemma>
- Community B70 llama.cpp notes:
  <https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes>
