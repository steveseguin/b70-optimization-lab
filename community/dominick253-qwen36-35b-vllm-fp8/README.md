# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

Deployable vLLM Docker recipe for serving `Qwen3.6-35B-A3B` in FP8 quantization on Intel Arc B70 with thinking mode and reasoning support.

## Status

> **Pending benchmark results.** Initial smoke tests pass. Full benchmark suite will be run and added to this PR when available.

## Model

- HF repo: `Qwen/Qwen3.6-35B-A3B` (full BF16 checkpoint)
- Quantization: in-place FP8 via `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`
- Docker image: `intel/llm-scaler-vllm:0.21.0-b1`

## One-Command Start

Requires two Intel Arc B70 GPUs visible at `/dev/dri`, Docker, and the model downloaded locally.

```bash
# --- Abstracted top-level variables ---
MODEL_HOST_DIR=/home/dom/llm-scaler-prod/models/Qwen3.6-35B-A3B
PORT=8001
TP=2
IMAGE="intel/llm-scaler-vllm:0.21.0-b1"
MAX_LEN=262144
MAX_SEQS=4
EAGER=1
THINKING_BUDGET=2048
# --- End variables ---

bash vllm-qwen36-35b-fp8.sh
```

## Launch Script

See `vllm-qwen36-35b-fp8.sh` for the full launcher with:
- Port 8001 ownership check and auto-stop of competing llama.cpp service
- Stale container cleanup
- Health check loop with startup monitoring
- Smoke tests (plain + thinking)

## Environment

| Field | Value |
| --- | --- |
| OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-28-generic |
| CPU | AMD Ryzen 9 9950X (16 cores) |
| GPU | 2x Intel Arc B70 (Battlemage G31), PCIe 4.0 x8 |
| VRAM | 32 GB per card (64 GB total) |
| Driver | xe |
| Runtime | vLLM 0.21 via `intel/llm-scaler-vllm:0.21.0-b1` |
| Model | Qwen3.6-35B-A3B (35B total, 3B active MoE) |
| Quantization | FP8 (in-place, per-tensor, BF16 -> FP8) |
| Context | 256K tokens (262144) |
| Tensor parallelism | TP=2 (both GPUs) |
| Thinking mode | enabled via chat template kwargs |
| Reasoning parser | qwen3 |
| Sampling | temp 1.0, top_p 0.95, top_k 20, min_p 0.0 |
| Max sequences | 4 |
| Eager mode | enabled (EAGER=1) |

## Key Design Decisions

- **Full BF16 checkpoint, NOT pretrained FP8**: The released 0.21 image lacks block-scaled XPU FP8 kernels. Pretrained-FP8 falls back to BF16/slow/garbage.
- **In-place FP8 quant**: `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1` stages weights in system RAM, then quantizes to native per-tensor FP8 in place. No VRAM spike, correct scales.
- **Intel XPU reference path**: `--dtype float16 --quantization fp8` uses the official Intel XPU FP8 backend.
- **Non-greedy thinking**: Greedy decoding breaks thinking mode. Using Qwen official config with `temperature=1.0`, `top_p=0.95`, `min_p=0.0`.
- **Eager mode**: `--enforce-eager` enabled for stability during initial testing.

## Reasoning / Thinking Mode

- `enable_thinking=true` via `--default-chat-template-kwargs`
- `thinking_token_budget=2048` per request (vLLM 0.21 hard budget)
- Reasoning parser: `qwen3` via `--reasoning-parser qwen3`
- Preserve thinking: `preserve_thinking=true` in chat template kwargs

## Notes

- Model directory must be mounted read-only: `-v ${MODEL_HOST_DIR}:/model:ro`
- Port 8001 is the default; change via `PORT` variable
- Service auto-stops any existing `llama-qwen36-35b.service` on port 8001 before launching
