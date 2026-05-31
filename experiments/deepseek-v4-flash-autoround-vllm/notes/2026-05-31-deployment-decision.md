# 2026-05-31 Deployment Decision

## Decision

Do not download or deploy `Intel/DeepSeek-V4-Flash-W4A16-AutoRound` on the
current 4x Intel Arc Pro B70 32 GB host.

The model is an INT4/W4A16 AutoRound checkpoint, but the resident weight size is
too large for a clean full-GPU TP4 vLLM deployment on 128 GB aggregate VRAM.

## Current Metadata Check

Checked via Hugging Face model metadata on 2026-05-31:

- repo: `Intel/DeepSeek-V4-Flash-W4A16-AutoRound`
- revision: `d8ac6c04e22da23f68f797884471dae5cb129ee0`
- public: true
- gated: false
- last modified: `2026-05-06T05:56:30+00:00`
- safetensor shards: `46`
- safetensor bytes: `152,946,418,392`
- safetensor size: `142.44 GiB`
- equal TP4 weight split floor: `35.61 GiB` per GPU before runtime overhead

The B70 cards have 32 GB each. vLLM also needs allocator headroom, KV cache,
graph/capture memory, communication buffers, and kernel scratch. So this is over
budget before any useful context length is allocated.

## Support Status

The Hugging Face model card currently says the AutoRound checkpoint is not
supported by vLLM or SGLang and points users to the repository's `inference/`
folder instead. The local vLLM tree has `DeepseekV4ForCausalLM`, but that does
not make this specific W4A16 AutoRound checkpoint viable on the B70/XPU path.

## Deployment Consequence

No download was started. Pulling the full checkpoint would consume roughly
143 GiB of model storage and still leave us unable to deploy it full-resident on
the available VRAM.

## Revisit Conditions

Revisit only if one of these changes:

- hardware changes to at least 8x 32 GB or 4x 48/64 GB GPUs;
- a smaller DeepSeek V4 Flash quant appears with a resident size below roughly
100 GiB and a compatible vLLM/XPU loader;
- we decide to build an expert offload/paging path and accept that it is a
separate latency class;
- vLLM/XPU support for this exact AutoRound DeepSeek V4 checkpoint lands and a
partial/offloaded placement strategy is available.

## More Plausible Next Candidates

- Step 3.7 Flash NVFP4 remains a tighter but potentially possible vLLM target
from the earlier notes.
- Step 3.7 Flash GGUF `Q4_K_S` or `IQ4_XS` is more likely to fit, but it is a
llama.cpp/SYCL track, not vLLM.
- Continue optimizing the REAP MiniMax path if the goal is immediate measurable
throughput on this box.
