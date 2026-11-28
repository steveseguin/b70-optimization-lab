# Inkling-2-Mini UD-IQ4_XS — Own Xe Runtime Measurements (2026-11-28)

Measured on host `steve-TURIND8-2L2T` (6× Intel Arc Pro B70 32 GiB, Intel oneAPI 2026.1, Linux, `xe` driver) at commit `e50c0d8a930f27be04003cec576e4a82b5c3bc9b` (installed binary `/home/steve/inkling-serve/bin/ink_run`, SHA-256 `34754b9dcbdbf6702efa4a992b9926ff5ffe5ce30eab3389207a9dcfe804bf8e`).

## 1. Realistic Cold 12-Prompt Suite (One B70, OpenAI `/v1/chat/completions`, 512-Token Cap)

Four completely fresh OpenAI-compatible server processes (`serve/server.py` + `ink_run`, `ctx_tiers=[65536]`, `INK_SERVE_SNAP=0`, empty cache library, `--model inkling-2-mini-chat`, `--return-token-ids`, `--require-natural-eos`, `--max-tokens 512`). Every request verified `cached_tokens == 0`, `realistic_final_gate.passed == true`, and **0 GPU fault lines** in the kernel journal.

| Fresh Server | Mode | Class-Balanced 1–100 (tok/s) | Median 1–100 (tok/s) | Full After-TTFT Median (tok/s) | Wall Median (tok/s) | Median TTFT (ms) | VRAM @ 64K ctx (MiB) | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Server 1 (card 0) | Plain 1× B70 | **92.80** | 92.81 | 92.21 | 88.58 | 226.8 | 27,726 | [realistic-plain-server1-c0.json](realistic-plain-server1-c0.json) |
| Server 2 (card 2) | Plain 1× B70 | **92.77** | 92.79 | 92.19 | 88.54 | 227.1 | — | [realistic-plain-server2-c2.json](realistic-plain-server2-c2.json) |
| Server 1 (card 1) | DSpark (`INK_SPEC=7`) 1× B70 | **121.87** | 122.11 | 108.04 | 103.08 | 228.3 | 28,537 | [realistic-dspark-server1-c1.json](realistic-dspark-server1-c1.json) |
| Server 2 (card 3) | DSpark (`INK_SPEC=7`) 1× B70 | **124.79** | 125.12 | 110.56 | 105.38 | 227.7 | — | [realistic-dspark-server2-c3.json](realistic-dspark-server2-c3.json) |

**Exact bit-identity across all 4 servers:** All **12/12 prompts × 512 generated tokens (6,144 tokens per server)** produced **100% identical `token_ids` and output `sha256`** across Plain Server 1, Plain Server 2, DSpark Server 1, and DSpark Server 2.

## 2. Uncached Reading-Rate & TTFT Probe (`931` Input Tokens, `cached_tokens == 0`)

Captured on Batch 1 servers before the realistic suite ([prefill-512-probe.json](prefill-512-probe.json)):

| Mode | Prompt Tokens | Cached Tokens | Wall TTFT (s) | Reading Rate (prompt / TTFT) | Engine Read Rate (tok/s) | Token IDs Identical |
|---|---:|---:|---:|---:|---:|---|
| Plain (card 0) | 931 | 0 | 0.6474 | **1,438.1 tok/s** | **1,482.5 tok/s** | Yes (`16/16`) |
| DSpark (card 1) | 931 | 0 | 0.6757 | **1,377.8 tok/s** | **1,391.6 tok/s** | Yes (`16/16`) |

## 3. Direct Engine & Multi-Card Context Scaling Summary

Full chronological measurements and bit-exactness gates (`check-exact.sh`, 15/15 checks + `426/426` tensor dumps bit-identical against baseline v8) live in [`experiments/own-xpu-runtime/inkling2/SCOREBOARD.md`](../../experiments/own-xpu-runtime/inkling2/SCOREBOARD.md) and [`experiments/own-xpu-runtime/inkling2/data/scoreboard.csv`](../../experiments/own-xpu-runtime/inkling2/data/scoreboard.csv):

- **Single-card (`1× B70`) peak direct decode:** Plain **93.08 tok/s** (`code 256t`, R10c) / **86.46 tok/s** (3K, R10c); DSpark **150.55 tok/s** (`code 256t`, R10b-v2) / **123.73 tok/s** (3K, R10b-v2); 4-seq shared decode **160.7 tok/s**.
- **Single-card (`1× B70`) prompt reading:** 3K **1,981 tok/s**, 31K **1,548 tok/s**, 100K **1,207 tok/s** plain / **1,185 tok/s** DSpark, 200K **834 tok/s** plain / **825 tok/s** DSpark.
- **Six-card (`6× B70`, cuts `7,15,23,30,37`) split & shared KV:** 100K prompt **4,793.8 tok/s** plain / **4,568.2 tok/s** DSpark; 200K prompt **3,443.0 tok/s** plain / **3,390.8 tok/s** DSpark; 200K shared decode **62.0 plain / 91.2 DSpark**; **1M needle (1,042,081 tok) DSpark** prompt **891.6 tok/s**, 400t decode **68.59 tok/s** (both hidden facts exact, 0 faults).
