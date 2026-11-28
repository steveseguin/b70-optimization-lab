# Inkling-2-Mini B70 Scoreboard & Active Bottlenecks

Single-page operational summary for `experiments/own-xpu-runtime/inkling2/` (so agents do not have to parse the 150 KB chronological [`README.md`](README.md) on every turn). Machine-readable history lives in [`data/scoreboard.csv`](data/scoreboard.csv); closed ideas live in [`DO-NOT-REPEAT.md`](DO-NOT-REPEAT.md).

- **Model:** `unsloth/Inkling-2-Mini-GGUF` `UD-IQ4_XS` (`15.73 GB`, rev `45fd0876`) + `dspark-Inkling-2-Mini-Q8_0.gguf` (`0.40 GB`) + `mmproj-BF16.gguf`
- **Host & Cards:** `steve-TURIND8-2L2T` — **all 6 Intel Arc Pro B70 cards (`0–5`) authorized** (`f00b40a5a7` removed the model-introduced card-0 refusal; 6-card gate passed with 0 faults).
- **Exactness bar:** Bit-exact / lossless against baseline v8 (exact XMX NVFP4 experts + exact XMX Q8_0/Q6_K attention + exact XMX layers 20–23 experts, IEEE `-fp-model=precise`).

---

## Current Best Verified Numbers (as of 2026-11-27, commit `e25b20a655`)

### Single-Card Performance (1× B70)

| Context | Prompt (tok/s) | Plain Decode (tok/s) | DSpark Decode (tok/s) | Notes / Evidence |
|---|---:|---:|---:|---|
| Short (`haiku`/`code`) | — | 88.8–90.4 | 134.0–141.1 | Baseline v8 (`6cbce1f685`); v5→v6 plain slip `−1.7%` still open |
| 3K (`3,127` tok) | **1,889** | ~83.2 | ~110.6 | Baseline v8 (`6cbce1f685`), exact XMX |
| 31K (`31,270` tok) | **1,529** | ~70.5 | ~103.9 | Baseline v8 (`6cbce1f685`) |
| 100K | **1,035** | ~52.5–55.2 | **53.19** (512 tok) / **51.49** (1024 tok) | Calibrated DSpark + plain-streak skip (`e25b20a655`, +8.5% over static 47.42) |
| 200K | **727–761** | ~39.8 | **98.35** (512 tok) | Calibrated DSpark + plain-streak skip (`e25b20a655`, up from 88.69 static) |
| 530K needle | **351.6** | **22.5** | **45.8** (515K) | Fits on 1 card; both hidden facts exact |

### Multi-Card Split & Shared-Cache Performance (Host-Staged, 0 Card Faults)

| Topology | 100K Prompt | 200K Prompt | 200K Decode (Shared) | 1M Needle Prompt | 1M Decode Plain | 1M Decode DSpark |
|---|---:|---:|---:|---:|---:|---:|
| 2 cards (`1+2`) | 1,962 tok/s (1.89×) | 1,425 tok/s (1.99×) | 51.9 plain / 77.8 DSpark | 400.9 tok/s | 12.56 (19.37 first 200) | **33.97 tok/s** |
| 4 cards (`1–4`) | 3,588 tok/s (3.40×) | 2,786 tok/s (3.83×) | 59.4 plain / **84.9 DSpark** | 795.7 tok/s | 16.01 (28.18 first 200) | **48.18 tok/s** |
| 5 cards (`1–5`) | 3,857 tok/s (3.70×) | 2,964 tok/s (4.13×) | 54.7 plain / 79.7 DSpark | 812.8 tok/s | 16.64 (34.78 first 200) | **62.29 tok/s** |
| 6 cards (`0–5`) | **4,152.8 tok/s** | **3,226.3 tok/s** | — | — | — | — |

*(Serving default: `INK_SHARD_MIN=32768`, cards `0–5` enabled in `serve/config.json`, server stopped during optimization.)*

---

## Active Bottleneck Budget & Floors (Single Card)

- **Short-context 1-token decode (~11.21 ms/step, 791 launches/step, 98% GPU busy):**
  - `moe_gate_up`: **2.65 ms** (48 launches, ~55.2 µs each; NVFP4 4-bit decode instruction-bound, ~170 instr/step)
  - `w:attn_in_xe`: **1.87 ms** (48 launches, ~39.0 µs each)
  - `moe_down`: **1.36 ms** (48 launches, ~28.4 µs each; ~468 GB/s bench floor)
  - `w:attn_output` + norms/routing/conv/mix: **~5.1 ms**
  - **Open single-card decode leads:** recover the v5→v6 plain-decode `−1.7%` slowdown (~2% post-ESIMD kernel slowdown); reduce NVFP4 1-token decode instructions in `XFull`; calibrate/prune DSpark verification cost and multi-token check kernels (2–8 tokens).
- **Long-context prompts (power-bound at 275 W PL2, ~2.45–2.60 GHz):**
  - Judge prompt kernels by **Joules per launch**, not isolated wall time.
  - 100K budget: full attention ~41% (FP32 FMA ~79% peak), experts ~31% (exact DPAS ~24 pJ/MAC), attention matrices ~13%, `moe_tiles`/misc ~15%.
- **Long-context decode (>100K):**
  - Memory-bandwidth bound reading 32 KB/pos KV cache (`~518–533 GB/s` of 608 GB/s peak); primary gains come from DSpark acceptance/skip policy, multi-card KV sharing (`INK_SHARD_COPY`), and check-step attention efficiency.

---

## Standard Commands (Two-Tier Workflow)

```bash
# 1. Build (strict IEEE, ~15-60s)
experiments/own-xpu-runtime/inkling2/scripts/build.sh ink_run /home/steve/inkling-work/bin/ink_run_cand

# 2. Fast 1-card exactness screen (~60-90s, card 0 default)
experiments/own-xpu-runtime/inkling2/scripts/check-fast.sh /home/steve/inkling-work/bin/ink_run_cand 0

# 3. Parallel 6-card single-card experiment wave (cards 0-5 simultaneously)
experiments/own-xpu-runtime/inkling2/scripts/run-wave.sh /tmp/wave.arms /mnt/fast-ai/inkling-cache/tests/wave-out

# 4. Full 15-check exactness gate (winners only, 5 cards in parallel)
experiments/own-xpu-runtime/inkling2/scripts/check-exact.sh /home/steve/inkling-work/bin/ink_run_cand

# 5. Lint DO-NOT-REPEAT.md before committing any closed arm
experiments/own-xpu-runtime/inkling2/scripts/lint-do-not-repeat.py
```
