# Qwen3.6 35B A3B Q8_0 on 2x Intel Arc Pro B70 (llama.cpp SYCL)

Deployable llama.cpp SYCL recipe for serving `Qwen3.6-35B-A3B` in Q8_0
quantization across two Intel Arc Pro B70 GPUs using native SYCL (llama.cpp
Intel build).

## Status

- **Working** on 2x B70, tested 2026-07-25
- OpenAI-compatible endpoints: `0.0.0.0:8001` (GPU0), `0.0.0.0:8002` (GPU1)
- Served model names: `qwen36-35b-mtp`, `Qwen35B-GPU2`
- Max context: `524288` tokens (512K)
- Quantization: Q8_0 (weights and KV cache)
- Speculative decoding: draft-MTP2 (draft-n-max 2)
- Reasoning parser: enabled, 4096-token budget, "Thought complete, rendering
  final output."

## Model

- HF repo: `Qwen/Qwen3.6-35B-A3B` (via LMStudio download, Unsloth Dynamic 2.0 GGUF)
- GGUF file: `Qwen3.6-35B-A3B-Q8_0.gguf` (37GB)
- mmproj: `mmproj-BF16.gguf` (861MB)

## One-Command Start

Requires llama.cpp built with SYCL support, two Intel Arc Pro B70s visible at
`/dev/dri`, and the model downloaded locally.

### GPU 0 (port 8001)

```bash
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export ZE_AFFINITY_MASK=0
export ZES_ENABLE_SYSMAN=1
export GGML_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
export ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.1/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/mkl/2026.1/lib:$LD_LIBRARY_PATH

llama-server \
  --model /path/to/Qwen3.6-35B-A3B-Q8_0.gguf \
  --mmproj /path/to/mmproj-BF16.gguf \
  --alias qwen36-35b-mtp \
  --host 0.0.0.0 --port 8001 \
  --gpu-layers 99 \
  --threads 16 \
  --ctx-size 524288 \
  -np 2 \
  -ctk q8_0 \
  -ctv q8_0 \
  --batch-size 2048 \
  --ubatch-size 512 \
  --reasoning on \
  --reasoning-preserve \
  --reasoning-budget 4096 \
  --reasoning-budget-message "Thought complete, rendering final output." \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --spec-type draft-mtp \
  --spec-draft-n-max 2
```

### GPU 1 (port 8002)

Same as above but with:

```bash
export ONEAPI_DEVICE_SELECTOR=level_zero:1
export ZE_AFFINITY_MASK=1
--alias Qwen35B-GPU2 \
--port 8002
```

## systemd Services

Two systemd units are provided for persistent operation:

- `llama-qwen36-35b-mtp.service` — GPU0, port 8001
- `llama-qwen36-35b-mtp-2.service` — GPU1, port 8002

Both run as user `dom`, group `dom`, with supplementary groups `render video`.
Restart policy: `always`, restart delay 5s, start limit 300s.

## llama.cpp Build

- Source: `llama.cpp` commit `fb92d8f18`
- Build: `build-intel` (SYCL backend, IntelLLVM 2026.1.0)
- Binary: `llama-server` (510K, built with IntelLLVM 2026.1.0 for Linux x86_64)

## Environment

- OS: Ubuntu 26.04 LTS
- Kernel: 7.0.0-28-generic
- GPU driver: xe (Battlemage G31, 8086:e223)
- GuC: bmg_guc_70.bin version 70.58.0
- CPU: AMD Ryzen 9 9950X (16C/32T)
- RAM: 60GB
- GPUs: 2x Intel Arc Pro B70 (32GB each)
  - GPU0: PCIe slot 03:00.0
  - GPU1: PCIe slot 08:00.0

## Notes

- MTP speculative decoding (draft-n-max 2) provides acceleration over target
  model alone.
- 512K context window requires large `--ctx-size`; KV cache uses Q8_0 for
  precision.
- The model is a 35B total / 3B active MoE architecture — not all parameters
  fire per token.
- Reasoning mode is enabled by default with a 4096-token thinking budget.
- `--reasoning-preserve` keeps thought content in the response.
- Both GPUs run independently on separate ports; no tensor parallelism between
  them (each serves the full model).
- Q8_0 quantization used for production/harder prompts — provides better
  quality than Q4 variants at the cost of higher memory usage.
- Unsloth Dynamic 2.0 GGUF format with Apache 2.0 license (Qwen3.6).
