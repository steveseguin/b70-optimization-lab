# Qwen3.6 35B A3B Q8_0 on Intel Arc B70 (llama.cpp SYCL)

Deployable llama.cpp SYCL recipe for serving `Qwen3.6-35B-A3B` in Q8_0
quantization on Intel Arc B70 with MTP speculative decoding.

## Model

- HF repo: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` (MTP variant with nextn head)
- GGUF: `Qwen3.6-35B-A3B-Q8_0.gguf` (from MTP repo)
  - Download: `https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf?download=true`
- mmproj: `mmproj-BF16.gguf` (from same repo)

## One-Command Start

Requires llama.cpp built with SYCL support, Intel Arc B70 visible at
`/dev/dri`, and the model downloaded locally.

```bash
# --- Abstracted top-level variables ---
LLAMA_SERVER=/path/to/llama.cpp/build/bin/llama-server
MODEL_DIR=/path/to/models/Qwen
MODEL="${MODEL_DIR}/Qwen3.6-35B-A3B-Q8_0.gguf"
MMPOJ="${MODEL_DIR}/mmproj-BF16.gguf"
PORT=8001
CTX=512000
SLOTS=2
ONEAPI_ROOT=/opt/intel/oneapi
# --- End variables ---

source "${ONEAPI_ROOT}/setvars.sh" --force >/dev/null 2>&1
export LD_LIBRARY_PATH="${ONEAPI_ROOT}/compiler/2026.1/lib:${ONEAPI_ROOT}/dnnl/2026.0/lib:${ONEAPI_ROOT}/mkl/2026.1/lib:$LD_LIBRARY_PATH"
export ZES_ENABLE_SYSMAN=1
export GGML_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
export ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1
export ZE_AFFINITY_MASK=0,1

exec "${LLAMA_SERVER}" \
  --model "${MODEL}" \
  --mmproj "${MMPOJ}" \
  --alias qwen36-35b-mtp \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --gpu-layers 99 \
  --threads 16 \
  --ctx-size "${CTX}" \
  -np "${SLOTS}" \
  --batch-size 2048 \
  --ubatch-size 512 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --repeat-penalty 1.0 \
  --presence-penalty 0.0 \
  --spec-type draft-mtp \
  --spec-draft-n-max 3 \
  --reasoning on \
  --reasoning-preserve \
  --reasoning-budget 2048 \
  --reasoning-budget-message "Thought complete, rendering final output." \
  --jinja
```

## systemd Service

```ini
[Unit]
Description=Qwen3.6-35B-A3B llama-server on Intel Arc B70
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/scripts
ExecStart=/bin/bash /path/to/scripts/llama-qwen36-35b.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=llama-qwen36-35b

Environment=PATH=/opt/intel/oneapi/compiler/2026.1/bin:/opt/intel/oneapi/dnnl/2026.0/bin:/opt/intel/oneapi/mkl/2026.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.1/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/mkl/2026.1/lib
Environment=ZE_AFFINITY_MASK=0,1
Environment=ZES_ENABLE_SYSMAN=1
Environment=GGML_SYSMAN=1
Environment=UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
Environment=GGML_SYCL_ENABLE_FLASH_ATTN=1
Environment=ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1

NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/path/to/scripts
PrivateTmp=true
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
```

## Launch Script (llama-qwen36-35b.sh)

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Abstracted top-level variables ---
LLAMA_SERVER=/path/to/llama.cpp/build/bin/llama-server
MODEL_DIR=/path/to/models/Qwen
MODEL="${MODEL_DIR}/Qwen3.6-35B-A3B-Q8_0.gguf"
MMPOJ="${MODEL_DIR}/mmproj-BF16.gguf"
PORT=8001
CTX=512000
SLOTS=2
ONEAPI_ROOT=/opt/intel/oneapi
# --- End variables ---

ONEAPI_SETUP() {
  set +u
  source "${ONEAPI_ROOT}/setvars.sh" --force >/dev/null 2>&1
  set -u
  export LD_LIBRARY_PATH="${ONEAPI_ROOT}/compiler/2026.1/lib:${ONEAPI_ROOT}/dnnl/2026.0/lib:${ONEAPI_ROOT}/mkl/2026.1/lib:$LD_LIBRARY_PATH"
  export ZES_ENABLE_SYSMAN=1
  export GGML_SYSMAN=1
  export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
  export GGML_SYCL_ENABLE_FLASH_ATTN=1
  export ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1
}

echo "=== Killing existing llama-server on port ${PORT} ==="
pkill -9 -f "llama-server.*${PORT}" 2>/dev/null || true
sleep 1

echo "=== Starting Qwen3.6-35B-A3B with MTP on 2x B70 ==="
echo "   Model: ${MODEL}"
echo "   Port:  ${PORT}"
echo "   Context: ${CTX}"
echo "   Slots: ${SLOTS}"
echo "   MTP: draft-mtp n-max=3"
echo ""

ONEAPI_SETUP
export ZE_AFFINITY_MASK=0,1

exec "${LLAMA_SERVER}" \
  --model "${MODEL}" \
  --mmproj "${MMPOJ}" \
  --alias qwen36-35b-mtp \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --gpu-layers 99 \
  --threads 16 \
  --ctx-size "${CTX}" \
  -np "${SLOTS}" \
  --batch-size 2048 \
  --ubatch-size 512 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --repeat-penalty 1.0 \
  --presence-penalty 0.0 \
  --spec-type draft-mtp \
  --spec-draft-n-max 3 \
  --reasoning on \
  --reasoning-preserve \
  --reasoning-budget 2048 \
  --reasoning-budget-message "Thought complete, rendering final output." \
  --jinja
```

## Environment

| Field | Value |
| --- | --- |
| OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-28-generic |
| CPU | AMD Ryzen 9 9950X (16 cores) |
| GPU | 2x Intel Arc B70 (Battlemage G31, 8086:e223), PCIe 4.0 x8 |
| VRAM | 32 GB per card (64 GB total) |
| Driver | xe |
| Runtime | llama.cpp fb92d8f18 (IntelLLVM 2026.1.0, SYCL backend) |
| Model | Qwen3.6-35B-A3B (35B total, 3B active MoE) |
| Quantization | Q8_0 weights, Q8_0 KV cache |
| Model size | 39 GB on disk |
| Context | 512K tokens (512000) |
| Speculative decoding | draft-MTP n-max=3 |
| Reasoning | enabled, 2048-token budget, --reasoning-preserve |
| Sampling | temp 0.6, top_p 0.95, top_k 20, min_p 0.0 |
| Concurrency | 2 request slots (-np 2) |
| Batch | batch_size=2048, ubatch_size=512 |

## Benchmark Results

Measured 2026-07-27 against live service on port 8001.

### Throughput

| Metric | Result |
| --- | --- |
| Output throughput (200 tok, avg) | **40.12 tok/s** |
| Output throughput range | 34.96 – 42.74 tok/s |
| Output throughput (512 tok, server log) | 43.75 tok/s |
| Prompt eval (short, 5 tok) | 2.1 tok/s (TTFT-dominant) |
| Prompt eval (medium, 23 tok) | 9.3 tok/s |
| Prompt eval (long, 96 tok) | 36.6 tok/s |
| Prompt eval (server log, 57 tok) | 117.47 tok/s |

First request is slower (~35 tok/s) due to graph compilation warm-up.
Subsequent requests stabilize at ~42.5 tok/s.

### MTP Speculation

| Metric | Result |
| --- | --- |
| Draft acceptance rate | **86.5%** (237/274) |
| Mean draft length | **1.86 tokens** |
| Graphs reused | **29,892** |

### Reasoning Mode

- Fully functional: structured `<think>...</think>` reasoning with proper tag delimiters
- Reasoning content served via `reasoning_content` field (not inline in `content`)
- Tested with math word problem: correctly identifies problem, breaks into steps, structured output

### GPU Status

| Field | Value |
| --- | --- |
| GPU 1 | 2800 MHz, 25.4 GB / 31.9 GB VRAM, 57°C, 5 W |
| GPU 2 | 2800 MHz, 27.6 GB / 31.9 GB VRAM, 59°C, 25 W |
| Service memory | 10.2 GB resident, 14.8 GB peak, 11.6 MB swap |

### Notes

- `--jinja` enables Jinja2 chat template
- `--spec-draft-n-max 3` with `--spec-type draft-mtp` enables MTP speculative decoding
- `--ctx-size 512000` sets 512K context window
- `-np 2` sets 2 request slots
- IMPORTANT: Must use the MTP variant from `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` — the standard
  Unsloth Q8_0 GGUF has no nextn/MTP tensors and `--spec-type draft-mtp` will fail
