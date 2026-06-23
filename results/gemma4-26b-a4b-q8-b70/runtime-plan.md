# Gemma 4 26B A4B Runtime Plan

## Primary Lane: llama.cpp SYCL GGUF

Start here because the user preference is Q8-quality GGUF, no TP split, and
single-session decode. A 27.6 GB Q8 GGUF should fit on a 32 GB B70 with limited
KV. Start at `CTX_SIZE=8192` to establish the baseline, then expand toward
32K only after the fit and canaries are proven. Use one process per GPU:

```bash
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 scripts/run-gemma4-26b-llamacpp-replica.sh
GPU_INDEX=1 PORT=18261 CTX_SIZE=8192 scripts/run-gemma4-26b-llamacpp-replica.sh
```

The quad launcher runs four independent replicas:

```bash
scripts/run-gemma4-26b-llamacpp-quad.sh
```

The first build was generic SYCL/JIT. The current promoted MTP lane uses the
B70 AOT build; use the `ocloc` spelling `bmg-g31`:

```bash
GGML_SYCL_DEVICE_ARCH=bmg-g31 \
BUILD_DIR=/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31 \
scripts/build-llama-cpp-sycl-b70.sh
```

Initial tuning axes:

- `-fa on` versus `-fa off`;
- `-ub 64/128/256/512` after the `64` baseline;
- `-b 512/1024/2048`;
- `GGML_SYCL_DISABLE_GRAPH=0/1`;
- `GGML_SYCL_DISABLE_DNN=0/1`;
- `GGML_SYCL_DISABLE_OPT=0` is the promoted speed path after repeated
  promotion-depth canaries. llama.cpp issue `#21893` still makes optimized
  SYCL a quality-risk family, so every new variant needs a full canary gate.
- f16 KV first, then q8 KV only if quality canaries stay stable.

Avoid llama.cpp multi-GPU tensor splitting initially. The point of this lane is
to remove PCIe collectives from the decode hot path.

## Secondary Lane: vLLM/XPU Int8 Per-Channel

vLLM's Gemma 4 recipe documents the 26B A4B model with
`--quantization int8_per_channel_weight_only`, explicitly because its expert
dimensions are sensitive to 4-bit quantization. This is the right vLLM precision
candidate if llama.cpp Q8 is too slow or lacks functionality.

Use **four independent DP=1 servers**, not one `--data-parallel-size 4` process:
there is a public vLLM Gemma 4 MoE DP issue whose workaround is separate
instances behind a load balancer. This also matches the no-PCIe-overhead goal.

Use the repo wrapper for reproducible runs and summary artifacts:

```bash
GPU_INDEX=0 PORT=18270 MAX_MODEL_LEN=8192 MAX_NUM_BATCHED_TOKENS=1024 \
CANARY_REPEATS=32 BENCH_REPEATS=8 \
scripts/run-gemma4-26b-vllm-int8pc-candidate.sh
```

The wrapper launches the local XPU vLLM environment with:

- `--quantization int8_per_channel_weight_only`;
- `--dtype bfloat16`;
- `--tensor-parallel-size 1 --pipeline-parallel-size 1`;
- `--max-num-seqs 1`;
- `--no-enable-prefix-caching`;
- `--language-model-only`;
- `--generation-config vllm`;
- one complete model replica on `ZE_AFFINITY_MASK=$GPU_INDEX`.

Start at 8K and graph off. If the baseline serves and passes canaries, test XPU
graph and batched-token sizes as separate candidates:

```bash
GPU_INDEX=1 PORT=18271 MAX_MODEL_LEN=8192 MAX_NUM_BATCHED_TOKENS=1024 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
CANARY_REPEATS=32 BENCH_REPEATS=8 \
scripts/run-gemma4-26b-vllm-int8pc-candidate.sh
```

Use this only from the local clean XPU vLLM virtualenv
(`/home/steve/.venvs/vllm-xpu`) and the official HF snapshot under
`/mnt/fast-ai/llm-cache/hf/`. Do not use the dirty Qwen source tree as a Gemma
baseline unless the vLLM package path is deliberately changed and recorded.

## Tertiary Lane: Ollama

Ollama can be useful as a convenience control for GGUF compatibility, but it is
not the first optimization target:

- less direct control over SYCL/B70 low-level flags;
- harder to preserve exact benchmark identity;
- may be useful to confirm chat template behavior or quality before deeper
  runtime work.

## Research Parallelism

Because the desired deployment is one replica per GPU, research should normally
use four disjoint attempts at once:

- GPU 0: current filled-long MTP control or one conservative `n=4` variant.
- GPU 1: draft budget / confidence-gate sweep around `n=4`.
- GPU 2: batch, ubatch, and polling sweep.
- GPU 3: candidate patch, alternative Q8 build, or vLLM comparison.

Record every attempt in the experiment folder, including failed launches and
bad quality results.
