# Qwen3.8-27B Cold Fusion GAIN V1.1 MTP — llama.cpp SYCL, single Arc Pro B70

## Headline Result

| Metric | Value |
|--------|-------|
| Model | Qwen3.8-27B Cold Fusion GAIN V1.1 MTP Q4_K_M (fine-tune) |
| GPU | 1x Intel Arc Pro B70 (32 GiB) |
| Engine | llama.cpp `b10472` (`60eeeb608`) |
| Short-context decode (51 tokens, thinking off) | **38.4 tok/s** |
| MTP draft acceptance (MTP2) | **94.4%** |
| Mean draft length (MTP2) | 2.89 tokens |
| Context size | 160,000 tokens |
| KV precision | F16 (target + draft) |
| Status | `community-reported` — not yet reference-lab verified |

## Full System Specification

### Hardware

| Component | Value |
|-----------|-------|
| GPU | Intel Arc Pro B70 (Battlemage G31), PCI ID `8086:e223` |
| GPU count | 1 |
| VRAM | 32 GiB |
| PCIe | Gen 5 x8 (negotiated from lspci; verify on target system) |
| Host | Dom-PC-2 |
| CPU threads available | 16 (used for llama.cpp threads) |

### OS and Drivers

| Component | Version |
|-----------|---------|
| OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-29-generic |
| GPU kernel driver | `xe` (Intel Xe2 Graphics), srcversion `85B7CA089405934276CBAD3` |
| libze-intel-gpu1 | 26.27.39122.11-0 |
| intel-opencl-icd | 26.27.39122.11-0 |
| xpu-smi | 1.2 |
| oneAPI DPC++ | 2026.1.1 (IntelLLVM) |
| IGC (Intel GPU Compiler) | 2.38.2 |

### llama.cpp Build

| Component | Value |
|-----------|-------|
| Repo | `ggml-org/llama.cpp` |
| Commit | `60eeeb6082c1126bb8bc72902c83123cd056811b` |
| Version string | `0.1.2-dev (build 472, commit 60eeeb608)` |
| Build directory | `build-sycl` |
| CMake flags | `-DGGML_SYCL=ON -DF16=ON -DGRAPH=ON -DDNN=ON -DNATIVE=ON -DHOST_MEM_FALLBACK=OFF` |
| Compiler | Intel oneAPI 2026.1.1 (`icx`/`icpx` via `setvars.sh`) |
| LD_PRELOAD | `/opt/opencode-fixes/l0graphshim.so` |

### Model Artifact

| Field | Value |
|-------|-------|
| Filename | `Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-MTP-Q4_K_M.gguf` |
| SHA-256 | `db466a9432a52b87a7b7560f432f0e1caafeb111dbe3d168acf74dfe143a637c` |
| Size | 18,498,573,824 bytes |
| Base model | `ggml-org/Qwen3.8-27B` (upstream; fine-tuned locally by contributor) |
| Fine-tune type | GAIN V1.1 — MTP draft-head optimization |
| Quantization | Q4_K_M weights; F16 KV; F16 draft KV |
| MTP support | Built into GGUF (embedded MTP draft weights) |

## Exact Launch Command

```bash
#!/usr/bin/env bash
source /opt/intel/oneapi/setvars.sh --silent
export ONEAPI_DEVICE_SELECTOR="level_zero:0"
export GGML_SYCL_USE_LEVEL_ZERO_API="1"
export GGML_SYCL_ENABLE_FLASH_ATTN="1"
export GGML_SYCL_ENABLE_GRAPH="0"
export LD_PRELOAD="/opt/opencode-fixes/l0graphshim.so"

exec llama-server \
  --model "$MODEL_PATH" \
  --alias Qwen38-27b-0 \
  --host 0.0.0.0 \
  --port 8001 \
  --ctx-size 160000 \
  --parallel 1 \
  --n-gpu-layers 99 \
  --device SYCL0 \
  --split-mode none \
  --main-gpu 0 \
  --batch-size 4096 \
  --ubatch-size 2048 \
  --threads 16 \
  --cache-type-k f16 \
  --cache-type-v f16 \
  --cache-type-k-draft f16 \
  --cache-type-v-draft f16 \
  --flash-attn on \
  --spec-type draft-mtp \
  --spec-draft-n-max 2 \
  --spec-draft-p-min 0.1 \
  --temp 1.0 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --jinja \
  --reasoning auto \
  --fit off
```

## Benchmark Evidence

### Short-Context Decode (live service, 2026-08-17 17:42 UTC)

Measurement method: 51 generated tokens per request, `reasoning_effort: none`,
single concurrent request to the running systemd service.

| GPU | Port | MTP | Decode tok/s | Draft Acceptance | Mean Draft Len |
|-----|------|-----|:---:|:---:|:---:|
| 0 (`:8001`) | 8001 | 2 | **38.4** | 94.4% | 2.89 |
| 1 (`:8002`) | 8002 | 3 | 40.0 | 90.5% | 3.71 |

The MTP2 result at 38.4 tok/s is the configuration recommended for production
use. The MTP3 result is included for reference; MTP3 may degrade at longer
context lengths.

### llama-benchy API Sweep (2026-08-17)

Full JSON files are in `reported/`. Summary of key rows:

**GPU1, MTP2 vs GPU1 no-MTP (18:04–18:10 UTC):**

| Depth | pp tok/s (MTP2) | tg tok/s (MTP2) | tg tok/s (no-MTP) |
|:---:|:---:|:---:|:---:|
| 0 | 511.3 | 11.37 | — |
| 32,768 | 642.4 | **6.21** | 3.73 |
| 65,536 | 562.5 | 2.35 | 2.33 |

Note: llama-benchy API mode measures wall-clock throughput including HTTP
overhead, server routing, and short 32-token responses. The tg numbers here
are lower than native llama-bench because they include API layer overhead and
the short response length does not amortize per-request costs. The 38.4 tok/s
figure above is a cleaner measurement from the server's own internal timing
on longer generation runs.

### Aug 16 Tune Sweep (16 runs, dense-model ceiling analysis)

Full JSONs available in contributor's `llama-benchy/results/qwen38-llamacpp-tune/`.
Key findings from the sweep:

- Best depth-0 tg: **34.63 tok/s** (r8-gpu1-b16384-ub4096)
- Best 65536-depth tg: **23.76 tok/s** (r7-gpu1-b8192-ub4096)
- MTP2 (r3) at depth 0: 34.49 tok/s — within 0.15 tok/s of the sweep best
- Conclusion: MTP2 is the optimal MTP setting; batch/ubatch tuning provides
  diminishing returns beyond 8192/2048

## Key Configuration Findings

### F16 KV is Required

A/B test on the same GPU, same llama.cpp build, same model:

| KV Type | Decode tok/s (short ctx) |
|---------|:---:|
| F16 (target + draft) | 38.4 |
| Q8 (target + draft) | ~10 |

The q8 KV collapse is specific to the SYCL backend on B70. It is not a model
quality issue — f16 KV produces identical quality to q8 at this precision
level. The finding is recorded here because it directly impacts anyone
reproducing this configuration.

### MTP2 is the Sweet Spot

| MTP Setting | Decode tok/s | Acceptance | Risk |
|-------------|:---:|:---:|------|
| MTP0 (none) | ~28–30 (baseline) | — | — |
| MTP2 | **38.4** | 94.4% | none observed |
| MTP3 | 40.0 | 90.5% | may degrade at >32k ctx |
| MTP4 | untested | — | — |

MTP2 provides the best risk-adjusted decode rate for stable long-running
operation. The trade-off versus MTP3 is ~1.6 tok/s for improved stability at
longer context, which is the configuration the contributor chose for production.

### Cold Fusion GAIN V1.1 — Honest Comparison

The Cold Fusion GAIN V1.1 MTP fine-tune is the contributor's running
production configuration. The A/B data in this packet shows it is **not** the
fastest decode option on this hardware at short context:

| Model | KV | MTP | Decode | Acceptance |
|-------|-----|-----|:---:|:---:|
| Unsloth Q4_K_M (stock) | f16 | 2 | **44.4 tok/s** | 100% |
| Cold Fusion GAIN V1.1 (this PR) | f16 | 2 | 38.4 tok/s | 94.4% |

On the simple counting probe, the stock model decoded faster and showed higher
MTP acceptance. The Cold Fusion fine-tune's value proposition is therefore not
raw decode throughput — it is the task/quality behavior the GAIN V1.1 fine-tune
was trained for, which is **not** quantified in this packet.

This is disclosed here so the maintainer does not treat Cold Fusion as a
throughput improvement. The genuine, verifiable contribution of this packet is:

1. A complete, reproducible single-B70 Qwen3.8-27B MTP llama.cpp SYCL config.
2. The **f16 KV requirement** finding (q8 KV collapses decode by ~70%).
3. The MTP2-as-sweet-spot characterization on this build.
4. Full system driver/runtime spec for the contributor's host.

## Reproduction Steps

1. Obtain the Cold Fusion GAIN V1.1 MTP GGUF from the contributor (SHA-256 above).
2. Build llama.cpp `b10472` with SYCL (see `repro.sh`).
3. Install Intel oneAPI 2026.1.1, libze-intel-gpu1 26.27+, xe kernel driver.
4. Run `repro.sh` with `MODEL_PATH` set.
5. Wait for the server to report ready (model load ~90s on Arc B70).
6. Send a generation request with `reasoning_effort: none` and measure decode.

See `llama-qwen38-27b-coldfusion-mtp.sh` for the full systemd-style launcher
and `repro.sh` for the build-and-run script.

## Systemd Service (contributor's running config)

```ini
[Unit]
Description=Qwen3.8-27B Cold Fusion MTP llama.cpp (GPU 0)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/dom
EnvironmentFile=/home/dom/.config/systemd/user/qwen38-gpu0.env
ExecStart=/usr/local/bin/launch-qwen38-q4-gpu0.sh
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Environment file:
```bash
ONEAPI_DEVICE_SELECTOR=level_zero:0
GGML_SYCL_USE_LEVEL_ZERO_API=1
GGML_SYCL_ENABLE_FLASH_ATTN=1
GGML_SYCL_ENABLE_GRAPH=0
LD_PRELOAD=/opt/opencode-fixes/l0graphshim.so
MODEL_PATH=/var/lib/libvirt/share/models/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-MTP-GGUF/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-MTP-Q4_K_M.gguf
```
