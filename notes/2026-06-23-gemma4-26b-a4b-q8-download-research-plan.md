# Gemma 4 26B A4B Q8 Download-Time Research Plan

Date: 2026-06-23

## Context

The Qwen3.6 35B TP4 lane is closed for now. The new target is
`gemma-4-26B-A4B-it` on Intel Arc Pro B70 with one complete model replica per
GPU, avoiding tensor-parallel PCIe overhead. The first precision target is
Q8/INT8-or-better; INT4 AutoRound and Q4-family GGUFs are not acceptable as the
default quality lane.

The primary GGUF download is in progress:

```text
repo: unsloth/gemma-4-26B-A4B-it-GGUF
revision: 3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a
file: gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
size: 27,636,230,944 bytes
destination: /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/
```

Hugging Face credentials are local-only under `/home/steve/.config/huggingface/`
and are ignored by Git.

## Research Findings

- Unsloth provides the Q8 target, a smaller Q8_0 control, Q6 side files, MXFP4
  side files, MTP draft files, and mmproj files in the same GGUF repo.
- Google model-card facts to preserve in run packets: 25.2B total parameters,
  3.8B active parameters, 30 layers, 1024-token sliding window, 256K context,
  128 total experts with 8 active experts plus 1 shared expert, and text+image
  modalities.
- llama.cpp server locally exposes MTP/speculative flags:
  `--spec-draft-model`, `--spec-type draft-mtp`, `--spec-draft-n-max`,
  `--spec-draft-device`, and `--spec-draft-ngl`.
- vLLM's Gemma 4 recipe recommends `--quantization int8_per_channel_weight_only`
  for 26B-A4B because the small MoE expert dimensions have excessive quality
  loss at 4-bit. This is the main fallback lane if llama.cpp Q8 disappoints.
- A vLLM Gemma 4 MoE issue reports `--data-parallel-size > 1` problems; use
  four separate DP=1 servers, not a single DP4 process.
- llama.cpp issue `#21893` reports B70/Gemma 4 nonsense output when optimized
  SYCL paths are enabled. Keep `GGML_SYCL_DISABLE_OPT=1` as the default and
  test `=0` only behind repeat canaries.
- Google's MTP overview warns that 26B-A4B MTP may not speed up batch-1 decode
  on hardware without enough parallelism because different draft tokens can
  activate different experts. MTP is a follow-up, not the first experiment.
- DiffusionGemma is a potentially interesting future speed lane based on the
  26B MoE family, but it is a different generation method and not the requested
  Q8 causal checkpoint.
- LocalMaxxing public context on 2026-06-23 shows Gemma 4 26B family top rows
  around 87-95 tok/s, but those rows are mixed hardware/precision and include
  lower-precision modes. They are speed pressure, not direct Q8 B70 comparisons.
- LocalMaxxing submission packets require `hfId`, `hardware`, `engineName`,
  `quantization`, `tokSOut`, and at least one secondary metric. For this lane,
  include model revision, llama.cpp commit, backend, prompt/output/context,
  exact engine flags, canary status, benchmark JSON path, and server log path.

## Local Changes Made

- Hardened `scripts/download-gemma4-26b-q8-gguf.sh`:
  - pinned repo revision;
  - resumable authenticated `curl` first;
  - exact primary Q8 byte-size validation;
  - metadata JSON writing;
  - Hugging Face fallback still validates size and metadata.
- Hardened `scripts/run-gemma4-26b-llamacpp-replica.sh`:
  - safer first-boot defaults: `CTX_SIZE=8192`, `UBATCH_SIZE=64`;
  - richer launch identity logging;
  - `exec` without a pipeline so quad PID files point at server processes;
  - optional `EXTRA_LLAMA_ARGS` hook for later MTP.
- Hardened `scripts/run-gemma4-26b-llamacpp-quad.sh` with PID cleanup traps.
- Updated `scripts/gemma4-text-canary.py`:
  - chat completions by default;
  - fixed seed in payload and result;
  - code canary added.
- Updated `scripts/bench-openai-single-decode.py`:
  - chat completions by default;
  - fixed seed and run identity;
  - explicit failure if `usage.completion_tokens` is missing unless marked
    diagnostic.
- Added result packet docs:
  - `results/gemma4-26b-a4b-q8-b70/model-options.md`;
  - `results/gemma4-26b-a4b-q8-b70/research-plan.md`.

## Next Commands After Download Completes

Start one conservative replica:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

Run the first gates:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --repeats 32 \
  --out data/gemma4-26b-a4b-q8-b70-chat-canary-32.json

python3 scripts/bench-openai-single-decode.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --prompt-tokens 512 \
  --max-tokens 512 \
  --repeats 8 \
  --out data/gemma4-26b-a4b-q8-b70-p512o512-chat-baseline.json
```

If 8K does not fit, retry 4K then 2K before reducing weight/KV precision. If it
passes, launch all four replicas and run the ranked sweeps in
`results/gemma4-26b-a4b-q8-b70/research-plan.md`.

## Download-Time Plan Update

When the Q8 file lands:

1. Verify exact bytes and write metadata JSON because the active manual `curl`
   command will not write downloader metadata by itself.
2. Run `scripts/run-gemma4-26b-first-baseline.sh` unchanged for a conservative
   one-GPU 8K baseline.
3. If the baseline is valid but slow, immediately use four replicas for the
   control / scheduling / runtime-flag / alternate-runtime split in the research
   plan.
4. If the baseline is invalid, inspect the raw outputs before changing speed
   flags. First suspects are chat-template behavior, `GGML_SYCL_DISABLE_OPT`,
   and server EOS/turn-token handling.
5. Do not submit to LocalMaxxing until chat canaries pass at promotion depth and
   the benchmark has real completion-token accounting.
