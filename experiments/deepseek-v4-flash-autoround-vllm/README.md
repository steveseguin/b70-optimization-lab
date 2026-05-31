# DeepSeek V4 Flash AutoRound vLLM/XPU Lab

This folder tracks the bring-up and optimization work for:

- Model: `Intel/DeepSeek-V4-Flash-W4A16-AutoRound`
- Base model: `deepseek-ai/DeepSeek-V4-Flash`
- Target runtime: vLLM on Intel XPU / Level Zero
- Initial hardware target: 4x Intel Arc Pro B70 32 GB
- Quantization: AutoRound W4A16, `bits=4`, `group_size=128`, symmetric GPTQ-style packing

The immediate goal is not only to run the model. The goal is to create the same
kind of loop that worked for MiniMax M2.7: loader repair, quality gates,
repeatable decode benchmarks, negative-result capture, promoted patch snapshots,
and LocalMaxxing submissions only when a result is defensible.

## Current Status

As of 2026-05-31, this is an initial research track.

Known from Hugging Face metadata and the local vLLM tree:

- The checkpoint is public and non-gated.
- The repository is large but smaller than the initial API `usedStorage` value
  suggested. Direct file listing reports about `153.0 GB` decimal / `142.4 GiB`
  of safetensors across 46 shards. Hugging Face's model API `usedStorage` value
  reports `303.7 GB`, which appears to be repository/backend storage accounting
  rather than bytes the download must place on disk.
- vLLM has a `DeepseekV4ForCausalLM` implementation in this checkout.
- The model card explicitly says vLLM and SGLang are not supported currently.
- The local `inc` quantization path already has the MiniMax-era XPU W4A16
  `FusedMoE` hook. That is useful, but DeepSeek V4 has separate attention,
  cache, hyper-connection, and sparse-indexing blockers.

## Folder Map

- `notes/`: chronological bring-up notes and failure reports.
- `ideas/`: short candidate optimizations before they are tested.
- `future-research/`: larger or lower-priority research threads.
- `past-efforts/`: imported summaries from related MiniMax/Qwen experiments.
- `results/`: experiment ledger, promoted result summaries, rejected results.
- `patches/`: patch snapshots or patch notes, including failed patches.
- `benchmarks/`: benchmark shapes, commands, parser notes, comparison policy.
- `configs/`: env files, vLLM argument sets, LocalMaxxing payload templates.
- `scripts/`: experimental helpers for download, smoke, benchmark, and payloads.
- `data/`: local JSON summaries and small metadata captures.
- `localmaxxing/`: queued payloads and response paths for this model.

## First Milestone

The first useful milestone is a single-token or short p64/n16 smoke through
vLLM/XPU TP4 using the AutoRound checkpoint, with the following proven:

1. The model config loads as `DeepseekV4ForCausalLM`.
2. AutoRound maps to `inc` and W4A16 weights are not silently dequantized.
3. MoE experts remain quantized through the XPU path.
4. DeepSeek V4 attention/cache code can execute on XPU or has a correctness
   fallback.
5. The output is non-empty and not obviously degenerate.

No LocalMaxxing submission should happen at this stage.

## Promotion Policy

A result can move from experimental to promoted only if it has:

- repeated benchmark measurements with warm/cold called out separately;
- exact command, env, vLLM git diff, and model revision recorded;
- quality smoke that checks for NUL/control characters and degeneration;
- no speculative decoding unless the target model verifies draft tokens;
- no expert dropping, smaller model substitution, or power-limit increase;
- LocalMaxxing payload and response archived under this folder or repo `data/`.

## Useful Entry Points

```bash
cd /home/steve/llm-optimizations/experiments/deepseek-v4-flash-autoround-vllm

# Download once storage is confirmed.
bash scripts/download-model.sh

# Experimental vLLM throughput wrapper. Expected to fail before XPU bring-up
# patches land; logs are still useful.
bash scripts/bench-vllm-deepseek-v4-flash-autoround-xpu.sh
```

## External References

- Hugging Face model: https://huggingface.co/Intel/DeepSeek-V4-Flash-W4A16-AutoRound
- Base model: https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- AutoRound: https://github.com/intel/auto-round
- Local vLLM checkout: `/home/steve/src/vllm`
- MiniMax reference lab: `/home/steve/llm-optimizations/repro/minimax-m27-b70-110tps-ubuntu24-20260523`
