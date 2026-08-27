# Flash-Next 51B PLE deployment audit

Date: 2026-08-27

## Official design

Qwen describes the 51B n-gram embedding as a lookup table that can be kept in
host memory while the required rows are asynchronously prefetched and
overlapped with early model computation. The official vLLM recipe likewise
requires at least 51 GB of host RAM for PLE offload and documents
`VLLM_PLE_CPU_OFFLOAD=1`. It does not document disk-backed vLLM inference.

Primary references:

- <https://github.com/QwenLM/Qwen3.8-Flash-Next>
- <https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next>
- <https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8>

Community llama.cpp/GGUF deployments may memory-map the lookup table from
NVMe and rely on the operating-system page cache. That is a different runtime
and should not be presented as the intended vLLM path. The attached model is
on an external NTFS USB volume, so direct disk lookup would be especially poor
as the B70 default even if a future runtime exposed it.

## Current B70 implementation

The accepted TP4 launcher does not enable `VLLM_PLE_CPU_OFFLOAD`. It uses the
generic selective UVA offloader for
`ple_embedding.ngram_embedding.weight` and `embed_tokens.weight`. Each rank
reports 12.22 GiB placed in host memory. Together the four TP shards keep the
full FP8 PLE table plus input-embedding shards resident in system RAM and
GPU-addressable after checkpoint load. Decode does not stream weights from the
USB checkpoint.

This is not yet equivalent to the official PLE worker:

- XPU dispatch selects `vllm/models/qwen4_exp/amd/ple_layer.py`;
- its `Qwen4ExpNGramEmbedding` is a regular `nn.Module`, not a
  `PleOffloadLayer`;
- the cross-process PLE worker and asynchronous result fan-out are implemented
  around `PleOffloadLayer` in the NVIDIA path;
- the official recipe itself says its initial optimized offload is NVIDIA-only.

The current XPU result is therefore a valid RAM-resident UVA deployment, but
it must not be described as proving asynchronous PLE prefetch/overlap.

## Performance-preserving next gate

Keep the accepted MTP0 and MTP1 stages and rates unchanged. Before changing
the production recipe, build a separate report-only XPU PLE-worker candidate
that:

1. loads only the four logical PLE shards once in host RAM;
2. performs row lookup in the host worker and transfers only selected output
   vectors to the owning B70 rank;
3. starts the lookup before the layer that consumes it and records wait time at
   the PLE boundary;
4. proves exact MTP0/MTP1 output parity and the same placement/cache identity;
5. compares matched p146/o256 and at least one prefill-heavy context row against
   the accepted UVA control.

Do not replace the UVA path unless the new implementation passes mechanism,
quality, repeated-serving, and matched performance gates. Do not use the USB
volume as a decode-time backing store for this experiment.
