# MiniCPM5-2B baseline identity audit — 2026-09-12

Read-only inspection of the downloaded model and current official documentation.
No weights loaded, GPU work, runtime changes, downloads, quantization or draft use.

## Identity

- Official final RL+OPD BF16 checkpoint, not Base/Midtrain/SFT:
  `openbmb/MiniCPM5-2B`, revision `12a3808a956f869c767195e9266b59c4d21d92e2`.
  Local HF metadata and current model API agree.
- Path: `/mnt/raid-models/models/intake-20260912/openbmb--MiniCPM5-2B`.
- Safetensors header inspection counted **2,516,756,480 elements, all BF16**.
  This checks metadata identity, not tensor hash integrity (download ledger owns it).
- Standard `LlamaForCausalLM`: 42 layers, hidden 2048, FFN 6144, Q heads 16,
  KV heads 2, head dim 128; vocabulary 130560; untied embeddings; SiLU;
  RMS epsilon 1e-6; RoPE theta 5,000,000 with no scaling; max positions 131072.
- Apache-2.0. No custom model code or trust-remote-code is necessary for target.

## Recommended baseline

Use the newly pulled, digest-resolved upstream **vLLM XPU** runtime with its stock
Llama implementation, one B70, TP1/PP1, original BF16 weights, BF16-family KV
(`--kv-cache-dtype auto` with BF16 model), no speculation or quantization, and
`--enforce-eager` initially. Record full image/source/kernel/torch/transformers
versions before loading; do not identify a mutable nightly tag as an exact runtime.
A vLLM image digest was not selected in this read-only model audit.

A concrete initial server profile, after resolving the runtime and free device:

```text
vllm serve /model --served-model-name MiniCPM5-2B \
  --dtype bfloat16 --tensor-parallel-size 1 --pipeline-parallel-size 1 \
  --kv-cache-dtype auto --max-model-len 8192 --max-num-seqs 1 \
  --gpu-memory-utilization 0.80 --enforce-eager --no-enable-prefix-caching
```

8192 is a bounded baseline context setting, not a claim that 128K was tested.
The 0.80 utilization is an initial engineering choice, not a measured optimum.
Pin batch-token scheduling settings after inspecting that runtime's defaults.
Use an isolated port and image-local clean environment; don't inherit Qwen overlay
flags. For example GDN/MTP-specific patches are irrelevant to this standard Llama.

For a second implementation sanity reference use official Transformers >=5.6
(the checkpoint records 5.6.2), original BF16, one explicit XPU device, eager
attention if practical, no `device_map=auto` CPU spill. This is a correctness
cross-check, not a throughput competitor. Cross-runtime floating-point token
identity is not guaranteed; performance promotion requires same-runtime target
oracle plus semantic checks, not silently declaring any cross-runtime difference
acceptable or treating BF16 alone as a proof of quality.

## Prompt and sampling identity

The local Jinja template emits a BOS token itself. Tokenizer config has
`add_bos_token=false` and `add_eos_token=false`; avoid manually adding BOS again.
Use `apply_chat_template` and record rendered prompt/token IDs. EOS IDs are
**1 and 130073**, pad ID 1; don't stop only on the tokenizer's textual `</s>`.

Generation prompt behavior is three-way:

- `enable_thinking=true`: assistant prefix followed by `<think>\n`.
- `enable_thinking=false`: assistant prefix followed by an empty think section.
- argument omitted: assistant prefix only. Omitted is not equivalent to true.

Use explicit **thinking=true** for the initial native reasoning quality track.
The official vLLM cookbook recommends this for 2B; its no-thinking sampling row is
for 1B, not a demonstrated equal-quality 2B mode. If a direct-answer track is later
wanted, qualify it separately rather than calling disabling reasoning lossless.
Preserve generated reasoning tokens in raw token arrays. Report answer completion
and TTFT separately from total decode speed; a response capped before `</think>`
is not a successful final answer. A 512-token performance fixture may be too short
for some reasoning quality tasks; record truncation and use a separate sufficiently
large quality cap instead of mistaking truncated thinking for correctness.

Official user-facing sampling: temperature 1.0, top_p 0.95, min_p 0.0. Repetition
penalty 1.05 is an optional troubleshooting suggestion, not the baseline default.
For deterministic same-runtime token gates explicitly use greedy generation
(temperature 0), repetition penalty 1.0, min_p 0.0, seed and output limits pinned;
label this as a lab deterministic gate, not publisher benchmark replication.
The generation config defaults to sampling, so an omitted temperature can change
an otherwise identical-looking run. Do not add repetition penalties in response
to errors without creating a separate run identity.

## Official support and caveats

Current primary sources:

- [Model card](https://huggingface.co/openbmb/MiniCPM5-2B/tree/12a3808a956f869c767195e9266b59c4d21d92e2)
- [OpenBMB vLLM cookbook](https://github.com/OpenBMB/MiniCPM/blob/310e3fce1d8378e26471577c55084ea44bd9c8c3/docs/deployment/vllm.md)
- [OpenBMB Transformers cookbook](https://github.com/OpenBMB/MiniCPM/blob/310e3fce1d8378e26471577c55084ea44bd9c8c3/docs/deployment/transformers.md)
- [vLLM supported models](https://docs.vllm.ai/en/latest/models/supported_models/)

Publisher documents vLLM >=0.21 native loading and Transformers >=5.6. This
establishes model architecture support, not measured B70 kernel correctness or
performance. The cookbook includes stale CUDA-era tool-parser release guidance;
do not copy its old CUDA fallback package pin to this XPU host. Native tool output
is XML-style, not Qwen JSON; future tool tests must use an appropriate parser.
DSpark/SGLang and converted GGUF are separate later lanes, not this reference.
