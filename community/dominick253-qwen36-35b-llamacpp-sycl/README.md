# Qwen3.6 35B A3B Q8_0 on Intel Arc B70 (llama.cpp SYCL)

Deployable llama.cpp SYCL recipe for serving `Qwen3.6-35B-A3B` in Q8_0
quantization on Intel Arc B70 with MTP speculative decoding.

## Model

- HF repo: `Qwen/Qwen3.6-35B-A3B`
- GGUF: `Qwen3.6-35B-A3B-Q8_0.gguf` (37GB)
- mmproj: `mmproj-BF16.gguf` (861MB)

## One-Command Start

Requires llama.cpp built with SYCL support, Intel Arc B70 visible at
`/dev/dri`, and the model downloaded locally.

```bash
LLAMA_SERVER=/path/to/llama.cpp/build/bin/llama-server
MODEL_DIR=/path/to/models/Qwen
MODEL="${MODEL_DIR}/Qwen3.6-35B-A3B-Q8_0.gguf"
MMPOJ="${MODEL_DIR}/mmproj-BF16.gguf"
PORT=8001
CTX=512000
SLOTS=2

source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.1/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/mkl/2026.1/lib:$LD_LIBRARY_PATH
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
  --reasoning-format deepseek \
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
WorkingDirectory=/home/dom/scripts
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
ReadWritePaths=/home/dom/scripts
PrivateTmp=true
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
```

## Environment

- OS: Ubuntu 26.04 LTS
- Kernel: 7.0.0-28-generic
- GPU: Intel Arc B70 (Battlemage G31, 8086:e223)
- Driver: xe
- CPU: AMD Ryzen 9 9950X (16 cores)
- Model: Qwen3.6-35B-A3B (35B total, 3B active MoE)
- Quantization: Q8_0 weights, Q8_0 KV cache
- Context: 512K tokens
- Speculative decoding: draft-MTP n-max=3
- Reasoning: deepseek format, 2048-token budget, --reasoning-preserve
- Build: llama.cpp fb92d8f18, IntelLLVM 2026.1.0

## Notes

- `--jinja` enables Jinja2 chat template
- `--reasoning-format deepseek` uses the DeepSeek-style reasoning parser
- `--reasoning-budget 2048` limits thinking content to 2048 tokens
- `--reasoning-preserve` keeps thought content in the response
- `--spec-draft-n-max 3` with `--spec-type draft-mtp` enables MTP speculative decoding
- `--ctx-size 512000` sets 512K context window
- `-np 2` sets 2 request slots
- Sampling: temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repeat_penalty 1.0
- 39GB model size on disk; Q8_0 quantization
