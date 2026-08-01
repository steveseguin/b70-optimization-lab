# Qwen3.6 35B A3B UD-Q8_K_XL on Intel Arc B70 (llama.cpp SYCL)

> **Maintainer note — community submission, not reproduced in the reference lab.**
>
> Read [`STATUS.md`](STATUS.md) before running this recipe. The contributor's
> environment and measurements are retained below as community-reported
> evidence. On 2026-08-01 the maintainer corrected the GGUF identity, the KV
> cache label, and unsafe launch defaults. The original submission called the
> model Q8_0 while linking UD-Q8_K_XL, called the implicit F16 KV cache Q8_0,
> enabled MTP by default, bound to `0.0.0.0`, ran systemd as root, and used
> `pkill -9`. The corrected recipe defaults to no MTP, loopback-only serving, a
> dedicated unprivileged service user, and no forced process termination.

---

This is a community-contributed llama.cpp SYCL recipe for serving
`Qwen3.6-35B-A3B` UD-Q8_K_XL on two Intel Arc B70 GPUs. The contributor later
reported that an MTP-off control was faster than the original MTP-on run, so
MTP is an optional diagnostic rather than the recommended default.

## Model

- HF repo: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`
- GGUF: `Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf`
  - Download: `https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf?download=true`
- mmproj: `mmproj-BF16.gguf` (from the same repo)

The linked artifact is UD-Q8_K_XL, not Q8_0. Record the model revision and file
checksum before treating runs on a later download as comparable.

For future maintainer validation, the locally pre-positioned artifact is pinned
to Hugging Face revision `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, size
`39099447584` bytes, and SHA-256
`6c6b816537abad90b250a0972b345466028d861ddfe316d5f0de31ca6440f781`.
It was identified but not loaded or executed during this review; this does not
prove that it is byte-identical to the contributor's benchmark artifact.

## One-Command Start

Requires llama.cpp built with SYCL support, Intel Arc B70 devices visible at
`/dev/dri`, and the model downloaded locally. This safe default listens only on
the local machine. Do not change `HOST` to `0.0.0.0` unless the endpoint is
protected by an authentication layer and host/network firewall appropriate to
the deployment.

```bash
# --- Abstracted top-level variables ---
LLAMA_SERVER=/path/to/llama.cpp/build/bin/llama-server
MODEL_DIR=/path/to/models/Qwen
MODEL="${MODEL_DIR}/Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"
MMPROJ="${MODEL_DIR}/mmproj-BF16.gguf"
HOST=127.0.0.1
PORT=8001
CTX=512000
SLOTS=2
ONEAPI_ROOT=/opt/intel/oneapi
# --- End variables ---

source "${ONEAPI_ROOT}/setvars.sh" --force >/dev/null 2>&1
export LD_LIBRARY_PATH="${ONEAPI_ROOT}/compiler/2026.1/lib:${ONEAPI_ROOT}/dnnl/2026.0/lib:${ONEAPI_ROOT}/mkl/2026.1/lib:${LD_LIBRARY_PATH:-}"
export ZES_ENABLE_SYSMAN=1
export GGML_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
export ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1
export ZE_AFFINITY_MASK=0,1

exec "${LLAMA_SERVER}" \
  --model "${MODEL}" \
  --mmproj "${MMPROJ}" \
  --alias qwen36-35b-ud-q8-k-xl \
  --host "${HOST}" \
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
  --reasoning on \
  --reasoning-preserve \
  --reasoning-budget 2048 \
  --reasoning-budget-message "Thought complete, rendering final output." \
  --jinja
```

No `-ctk` or `-ctv` option is supplied, so this recipe uses llama.cpp's
default F16 KV cache. A Q8 KV-cache run is a different quality and memory
configuration and must be labeled and validated separately.

## Optional MTP Diagnostic

To reproduce the contributor's original MTP-on configuration, add both flags
to either command:

```bash
  --spec-type draft-mtp \
  --spec-draft-n-max 3
```

Use the MTP GGUF variant above; a model without the required next-token tensors
will fail with `draft-mtp`. The contributor reported high draft acceptance,
but their later control was approximately 45 tok/s with MTP off versus 40 tok/s
with MTP on. Keep MTP off unless a controlled same-prompt A/B on the target
runtime demonstrates a benefit without a correctness regression.

## systemd Service

The original contribution used `User=root`. Root is unnecessary for normal
render-node access and substantially increases the impact of a compromised
model server. Create a dedicated `llama` service account, grant it only the
required `/dev/dri` access (commonly via the `render` group), and make the
runtime/model paths readable by that account before using this unit.

```ini
[Unit]
Description=Qwen3.6-35B-A3B llama-server on Intel Arc B70
After=network.target
Wants=network.target

[Service]
Type=simple
User=llama
Group=llama
SupplementaryGroups=render
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

## Launch Script (`llama-qwen36-35b.sh`)

This script does not kill an existing process. Stop the specifically managed
service cleanly before replacement; do not use a broad `pkill -9` expression,
which can terminate an unrelated server whose command line happens to match.
If the port is occupied, this launch should fail rather than silently taking
over another process.

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Abstracted top-level variables ---
LLAMA_SERVER=/path/to/llama.cpp/build/bin/llama-server
MODEL_DIR=/path/to/models/Qwen
MODEL="${MODEL_DIR}/Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"
MMPROJ="${MODEL_DIR}/mmproj-BF16.gguf"
HOST=127.0.0.1
PORT=8001
CTX=512000
SLOTS=2
ONEAPI_ROOT=/opt/intel/oneapi
# --- End variables ---

ONEAPI_SETUP() {
  set +u
  source "${ONEAPI_ROOT}/setvars.sh" --force >/dev/null 2>&1
  set -u
  export LD_LIBRARY_PATH="${ONEAPI_ROOT}/compiler/2026.1/lib:${ONEAPI_ROOT}/dnnl/2026.0/lib:${ONEAPI_ROOT}/mkl/2026.1/lib:${LD_LIBRARY_PATH:-}"
  export ZES_ENABLE_SYSMAN=1
  export GGML_SYSMAN=1
  export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
  export GGML_SYCL_ENABLE_FLASH_ATTN=1
  export ZE_COMMAND_QUEUE_SYNCHRONIZE_ASYNC=1
}

echo "=== Starting Qwen3.6-35B-A3B on 2x B70 ==="
echo "   Model: ${MODEL}"
echo "   Host:  ${HOST}"
echo "   Port:  ${PORT}"
echo "   Configured context ceiling: ${CTX}"
echo "   Slots: ${SLOTS}"
echo "   MTP: off (safe default)"
echo ""

ONEAPI_SETUP
export ZE_AFFINITY_MASK=0,1

exec "${LLAMA_SERVER}" \
  --model "${MODEL}" \
  --mmproj "${MMPROJ}" \
  --alias qwen36-35b-ud-q8-k-xl \
  --host "${HOST}" \
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
  --reasoning on \
  --reasoning-preserve \
  --reasoning-budget 2048 \
  --reasoning-budget-message "Thought complete, rendering final output." \
  --jinja
```

## Contributor Environment

The following values are contributor-reported and have not been reproduced in
the reference lab.

| Field | Value |
| --- | --- |
| OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-28-generic |
| CPU | AMD Ryzen 9 9950X (16 cores) |
| GPU | 2x Intel Arc B70 (Battlemage G31, 8086:e223), PCIe 4.0 x8 |
| VRAM | 32 GB per card (64 GB total) |
| Driver | xe |
| Runtime | llama.cpp fb92d8f18 (IntelLLVM 2026.1.0, SYCL backend) |
| Model | Qwen3.6-35B-A3B, `UD-Q8_K_XL` GGUF (35B total, 3B active MoE) |
| KV cache | F16 default; no `-ctk` or `-ctv` override was reported |
| Model size | approximately 39 GB on disk |
| Context | configured ceiling 512000; longest reported measured prompt was 96 tokens |
| Original speculative run | draft-MTP n-max=3 |
| Reasoning | enabled, 2048-token budget, `--reasoning-preserve` |
| Sampling | temp 0.6, top_p 0.95, top_k 20, min_p 0.0 |
| Concurrency | 2 request slots (`-np 2`) |
| Batch | batch_size=2048, ubatch_size=512 |

## Contributor-Reported Benchmark Results

Reported as measured on 2026-07-27 against the contributor's live service on
port 8001. No raw logs, request payloads, output hashes, or structured run
summary are included in this entry, so these values are not lab-verified.

### Throughput

| Metric | Contributor-reported result |
| --- | --- |
| Output throughput (200 tok, average, MTP on) | **40.12 tok/s** |
| Output throughput range (MTP on) | 34.96-42.74 tok/s |
| Output throughput (512 generated tok, server log, MTP on) | 43.75 tok/s |
| Later MTP-off control | approximately **45 tok/s** |
| Prompt eval (short, 5 tok) | 2.1 tok/s (TTFT-dominant) |
| Prompt eval (medium, 23 tok) | 9.3 tok/s |
| Prompt eval (longest reported measured prompt, 96 tok) | 36.6 tok/s |
| Prompt eval (server log, 57 tok) | 117.47 tok/s |

The contributor attributed the first-request result of approximately 35 tok/s
to graph compilation warm-up and reported subsequent requests near 42.5 tok/s.
The MTP-on average was approximately 11% slower than the later MTP-off control,
so the reported acceptance rate is not evidence of an end-to-end speedup.

`--ctx-size 512000` configures a maximum context allocation. It does not prove
correctness, stability, or usable performance at 512K tokens. The longest
reported measured prompt was 96 tokens; the 512-token row refers to generated
output length, not prompt/context validation.

### MTP-On Diagnostic

| Metric | Contributor-reported result |
| --- | --- |
| Draft acceptance rate | **86.5%** (237/274) |
| Mean draft length | **1.86 tokens** |
| Graphs reused | **29,892** |

### Reasoning Mode

The contributor reported:

- structured `<think>...</think>` delimiters;
- reasoning data in the `reasoning_content` field rather than inline in
  `content`;
- one math word-problem response that appeared correctly structured.

These observations are useful smoke evidence, not a broad correctness or
quality evaluation.

### GPU Status

| Field | Contributor-reported value |
| --- | --- |
| GPU 1 | 2800 MHz, 25.4 GB / 31.9 GB VRAM, 57 C, 5 W |
| GPU 2 | 2800 MHz, 27.6 GB / 31.9 GB VRAM, 59 C, 25 W |
| Service memory | 10.2 GB resident, 14.8 GB peak, 11.6 MB swap |

## Interpretation

- The contributor reported a working two-B70 llama.cpp/SYCL endpoint with this
  artifact and configuration.
- MTP acceptance was high, but the later contributor control indicates MTP was
  slower end to end in this setup. Acceptance rate alone is not a throughput
  result.
- The service was configured for a 512000-token ceiling, but only short prompts
  up to 96 tokens were reported as measured.
- Independent validation still needs exact source/model identities, cold and
  warm request separation, output/correctness artifacts, and same-prompt MTP
  on/off runs.
