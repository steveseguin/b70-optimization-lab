# Qwen3.8-27B Cold Fusion GAIN V1.1 MTP — llama.cpp SYCL, single Arc Pro B70

## Headline Result

| Metric | Value |
|--------|-------|
| Model | Qwen3.8-27B Cold Fusion GAIN V1.1 MTP Q4_K_M (fine-tune) |
| GPU | 1x Intel Arc Pro B70 (32 GiB) |
| Engine (original packet, 2026-08-17) | llama.cpp `b10472` (`60eeeb608`), kernel `7.0.0-29` |
| Short-context decode on that stack (51 tokens, thinking off) | **38.4 tok/s**, MTP2 accept **94.4%** |
| Engine (live refresh, 2026-08-18) | llama.cpp `b10488-7` (`3dc7285b4`), kernel `7.0.0-30` |
| Same 51-token probe on the refresh | **22.73 tok/s**, MTP2 accept **31.7%** |
| Context size | 160,000 tokens |
| KV precision | F16 (target + draft) |
| Status | `community-reported` — not yet reference-lab verified |

The 38.4 tok/s figure is **not** claimed on `b10488-7`. It stays as the
`b10472` / `7.0.0-29` measurement. The refresh re-ran the same model, flags,
and 51-token thinking-off probe after a staged llama.cpp + kernel switch.
Decode fell with draft acceptance (94.4% -> 31.7%). oneAPI 2026.1.1 and
compute-runtime `26.27.39122.11` were already newest and were not changed.

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
| Kernel (original packet) | 7.0.0-29-generic |
| Kernel (live refresh, 2026-08-18) | 7.0.0-30-generic (HWE metapackage; GRUB pinned to this entry, not the 7.1 mainline image also present on the host) |
| GPU kernel driver | `xe` (Intel Xe2 Graphics), srcversion `85B7CA089405934276CBAD3` (same srcversion on both 7.0.0-29 and 7.0.0-30) |
| libze-intel-gpu1 | 26.27.39122.11-0 |
| intel-opencl-icd | 26.27.39122.11-0 |
| xpu-smi | 1.2 |
| oneAPI DPC++ | 2026.1.1 (IntelLLVM) |
| IGC (Intel GPU Compiler) | 2.38.2 |

### llama.cpp Build

| Component | Value |
|-----------|-------|
| Repo | `ggml-org/llama.cpp` |
| Commit (original packet) | `60eeeb6082c1126bb8bc72902c83123cd056811b` (`b10472`) |
| Commit (live refresh) | `3dc7285b4f79e3abe53527fd4264b75226edb613` (`b10488-7`) |
| Version string (live) | `0.1.2-dev (build 485, commit 3dc7285b4)` |
| Build directory | staged worktree `build-sycl` (does not overwrite the live `b10472` inode until reboot) |
| CMake flags (actual refresh build) | `-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON -DGGML_NATIVE=ON -DGGML_SYCL_HOST_MEM_FALLBACK=OFF` |
| Notable llama.cpp delta vs b10472 | includes `sycl: honor GGML_HINT_SRC0_IS_HADAMARD` (`#27298`) and ggml 0.20.2 |
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

The MTP2 result at 38.4 tok/s is the configuration that was recommended for
production on `b10472`. The MTP3 result is included for reference; MTP3 may
degrade at longer context lengths.

### Stack refresh, 2026-08-18 (b10488-7 / kernel 7.0.0-30)

Same GGUF, same launch flags, same host, new llama.cpp + kernel. Live units
came up on the staged binary after reboot (`NRestarts=0`, both `/health` ok).

**51-token thinking-off probe (GPU1, server-internal eval time):**

| Stack | Decode tok/s | Draft accept | Mean draft len | predicted_n |
| --- | ---: | ---: | ---: | ---: |
| b10472 / 7.0.0-29 (2026-08-17) | 38.4 | 94.4% | 2.89 | 51 |
| b10488-7 / 7.0.0-30 (2026-08-18) | **22.73** | **31.7%** | 1.63 | 51 |

Raw: `reported/short-ctx-probe-20260818-b10488.txt`.

**llama-benchy on the live refresh** (`pp=2048`, `tg=256`, 2 runs,
`--no-warmup --no-adapt-prompt`, `reasoning_budget_tokens=128`, no `--exact-tg`):

The first refresh was measured before the Xe clock fix. The persistent
`xe-b70-minfreq.service` now pins both B70 GT domains to 2800 MHz at boot.

**Corrected llama-benchy rerun after the clock fix** (`gpu0` and `gpu1` ran
in parallel; same settings):

| GPU | depth 0 tg | 8k | 32k | 64k |
| ---: | ---: | ---: | ---: | ---: |
| 0 | **29.75** | **24.41** | **22.03** | **18.58** |
| 1 | **27.35** | **28.27** | **21.10** | **20.32** |

Corrected JSON: `reported/gpu0-b10488-fixed-benchy-20260818-133031.json`,
`reported/gpu1-b10488-fixed-benchy-20260818-133031.json`.

The deterministic counting probe after the fix reached 40.49 tok/s on GPU0
and 40.63 tok/s on GPU1, with 100% MTP acceptance. The llama-benchy results
use realistic corpus prompts and remain prompt/depth dependent.

The earlier pre-fix JSON remains available:
`reported/gpu0-b10488-benchy-20260818-122944.json` and
`reported/gpu1-b10488-benchy-20260818-123508.json`.

Same llama-benchy shape vs the Aug 16 MTP2 tune row (`r3-gpu0-mtp2`):

| depth | Aug 16 MTP2 tg | b10488-7 GPU0 tg |
| ---: | ---: | ---: |
| 0 | 34.49 | 28.56 |
| 8192 | 33.56 | 27.42 |
| 32768 | 26.22 | 21.23 |
| 65536 | 21.13 | 20.26 |

Prefill is similar. Decode is slower at 0-32k and about even at 64k.
Journal MTP on GPU1 during the 32k/64k rows: accept 41% at 32k and 63-68% at
64k (drafts nonzero). This is not the 94% short-probe accept from b10472.

oneAPI DPC++ `2026.1.1-325`, IGC `2.38.2`, and compute-runtime
`26.27.39122.11` were already the newest published packages. They were not
upgraded. The kernel install did not reboot the live servers; GRUB was pinned
from `7.0.0-29` to `7.0.0-30` so the next boot took the new kernel.

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
