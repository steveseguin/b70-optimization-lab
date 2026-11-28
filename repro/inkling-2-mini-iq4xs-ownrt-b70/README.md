# Inkling-2-Mini UD-IQ4_XS: Own Xe Runtime on One Intel Arc Pro B70

**Candidate · expert lab replay · lossless bit-exact Xe2 SYCL/ESIMD/XMX engine · OpenAI-compatible HTTP server.**

This recipe builds and runs our standalone C++/SYCL/ESIMD/XMX runtime ([`experiments/own-xpu-runtime/inkling2/`](../../experiments/own-xpu-runtime/inkling2/)) for Unsloth's `UD-IQ4_XS` quantization of Thinking Machines' **Inkling-2-Mini** (26.2B MoE, 5.4B active/token, looped middle layers, up to 530K context on one 32 GiB B70 or 1M context across 2–6 cards), with optional lossless **DSpark Q8_0** speculative decoding (`INK_SPEC=7`) that produces 100% bit-identical greedy tokens and logits.

## Verified Realistic-Suite Results (2026-11-28, Commit `e50c0d8a93`)

Measured across **four completely fresh OpenAI-compatible servers** (`serve/server.py`, 64K context tier, `INK_SERVE_SNAP=0`, empty cache library, `cached_tokens == 0` on every row, `--model inkling-2-mini-chat`, `--return-token-ids`, `--require-natural-eos`, 512-token cap, 0 GPU faults):

| Mode | Fresh Server 1 | Fresh Server 2 | Uncached Reading Probe (931 tok / wall TTFT) | VRAM @ 64K ctx |
|---|---:|---:|---:|---:|
| **Plain (1× B70)** | **92.80 tok/s** (c0, 1–100 class med; 92.21 full) | **92.77 tok/s** (c2, 1–100 class med; 92.19 full) | **1,438.1 tok/s** (1,482.5 engine, TTFT 0.647 s) | 27,726 MiB |
| **DSpark `INK_SPEC=7` (1× B70)** | **121.87 tok/s** (c1, 1–100 class med; 108.04 full) | **124.79 tok/s** (c3, 1–100 class med; 110.56 full) | **1,377.8 tok/s** (1,391.6 engine, TTFT 0.676 s) | 28,537 MiB |

**Lossless parity proof:** All **12/12 prompts × 512 tokens (6,144 generated tokens)** are **100% bit-identical (`token_ids` and `sha256`)** across both Plain servers and both DSpark servers. Direct engine CLI decode reaches **93.08 tok/s** plain and **150.55 tok/s** DSpark on `code` 256t, **160.7 tok/s** on 4-sequence shared decode, and **891.6 tok/s prompt / 68.59 tok/s decode** on a 1,042,081-token needle across 6× B70 cards (see [detailed results](../../results/inkling-2-mini-iq4xs-ownrt-b70/README.md) and [SCOREBOARD.md](../../experiments/own-xpu-runtime/inkling2/SCOREBOARD.md)).

## Requirements and Model Inputs

- **Hardware:** 1× Intel Arc Pro B70 32 GiB (or 2–6× B70 for split/1M context), Linux with `xe` kernel driver, ≥15 GiB host RAM.
- **Toolchain:** Intel oneAPI DPC++/C++ Compiler **2026.1** (`icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31`), Level Zero, Python 3.12 with `aiohttp` and `jinja2` for the OpenAI server.
- **Weights** ([`manifests/models.json`](manifests/models.json), revision `45fd08764f2b0bf16b03a5483a80e5c7aaec8772`):

```bash
hf download unsloth/Inkling-2-Mini-GGUF \
  --revision 45fd08764f2b0bf16b03a5483a80e5c7aaec8772 \
  --local-dir /mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF \
  Inkling-2-Mini-UD-IQ4_XS.gguf dspark-Inkling-2-Mini-Q8_0.gguf mmproj-BF16.gguf
```

## Build, Exactness Gate, and Launch

```bash
# 1. Build ink_run with strict IEEE FP32 numerics (one compile at a time on 15 GiB RAM)
experiments/own-xpu-runtime/inkling2/scripts/build.sh ink_run /home/steve/inkling-serve/bin/ink_run

# 2. Run fast 1-card exactness gate (haiku/code/DSpark/3K logits + journal fault check)
experiments/own-xpu-runtime/inkling2/scripts/check-fast.sh /home/steve/inkling-serve/bin/ink_run 0

# 3. Run full 15-check bit-exactness gate (426/426 tensor dumps, DSpark, 4-seq, vision)
experiments/own-xpu-runtime/inkling2/scripts/check-exact.sh /home/steve/inkling-serve/bin/ink_run

# 4. Launch OpenAI-compatible HTTP server (default port 8001; override config via INK_SERVE_CONFIG)
python3 experiments/own-xpu-runtime/inkling2/serve/server.py

# 5. Reproduce cold uncached 12-prompt realistic suite (set INK_SERVE_SNAP=0 in config engine_env)
python3 scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:8001 --model inkling-2-mini-chat --api-mode chat \
  --max-tokens 512 --return-token-ids --require-natural-eos \
  --out /tmp/inkling2-realistic.json
```

## Current Status and Remaining Gates

This package is retained at **`draft` / `candidate` (`lab-replay`)** status in this repository:
- All 15/15 engine exactness checks and 4 fresh-server realistic-suite gates (`cached_tokens == 0`, 0 GPU faults) passed on the lab host.
- Clean-host OS installation replay, independent full-512 external llama.cpp oracle attestation, and external `neural.download` release publication remain pending owner review.
