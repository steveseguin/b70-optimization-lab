# Inkling-2-Mini B70 Scoreboard & Active Bottlenecks

Single-page operational summary for `experiments/own-xpu-runtime/inkling2/` (so agents do not have to parse the 150 KB chronological [`README.md`](README.md) on every turn). Machine-readable history lives in [`data/scoreboard.csv`](data/scoreboard.csv); closed ideas live in [`DO-NOT-REPEAT.md`](DO-NOT-REPEAT.md).

- **Model:** `unsloth/Inkling-2-Mini-GGUF` `UD-IQ4_XS` (`15.73 GB`, rev `45fd0876`) + `dspark-Inkling-2-Mini-Q8_0.gguf` (`0.40 GB`) + `mmproj-BF16.gguf`
- **Host & Cards:** `steve-TURIND8-2L2T` — **all 6 Intel Arc Pro B70 cards (`0–5`) authorized** (`f00b40a5a7` removed the model-introduced card-0 refusal; 6-card gate passed with 0 faults).
- **Exactness bar:** Bit-exact / lossless against baseline v8 (exact XMX NVFP4 experts + exact XMX Q8_0/Q6_K attention + exact XMX layers 20–23 experts, IEEE `-fp-model=precise`).

---

## Current Best Verified Numbers (as of 2026-11-28, commit `11423897cd`)

### Single-Card Performance (1× B70)

| Context | Prompt (tok/s) | Plain Decode (tok/s) | DSpark Decode (tok/s) | Notes / Evidence |
|---|---:|---:|---:|---|
| Short (`haiku`/`code`) | — | **94.2–94.6** (**+1.69%** R11b 6/6 cards!) | **151.2–154.1** (**+0.98%** R11b on top of R11a!) | R11b (`11423897cd` `INK_MIX_FAST=1`: 6c mean **94.18**, c0 **94.55** plain; 6c mean **151.21**, c0 **154.13** / c3 **154.03** DSpark records!; `span 10.547 ms`); 4-seq **160.7 tok/s** |
| 3K (`3,127` tok) | **1,981** (`+full app 47` pruning) | **87.1–88.1** (**+1.66%** R11b 6/6 cards!) | **138.4–141.2** (`256t`, **+1.16%** R11b 6/6!) / **125.4** (`128t`) | R11b (c0 **88.12** 3K plain record!; `dspark3k` 256t 6c mean **138.43**, c0 **141.19**) + R11a (`128t` c0 **125.36**) + `137fc13c1c` (`long16 1,980.8`) |
| 31K (`31,270` tok) | **1,548+** (`+0.1–0.6%` SOA + `app 47`) | ~70.5+ | **119.7–124.0+** | Exact XMX + ESIMD pairs + `xd::splite3` + NVFP4 SOA + full `app 47` + `F32_HI16` |
| 100K | **1,110–1,207+** plain (`+0.87%` full `app 47`) / **1,089–1,185+** DSpark | ~52.8–54.8+ | **55.0–57.3** (`+F32_HI16`) | `137fc13c1c` (6/6 cards +0.87% 100K plain) + `a131fcb7ab` (+5.31%) + `edfd7f95bc` (+3.68% DSpark) |
| 200K | **777–834+** plain / **769–825+** DSpark (**+5.77%**) | ~40.9–41.1+ | **81.2–84.2+** (`c200k` 256t) / **98.4–99.6** | `137fc13c1c` + `a131fcb7ab` (+6.75% plain) + `edfd7f95bc` (+5.77% DSpark skip) + `9485a273ed` |
| 530K needle | **351.6+** | **22.5** | **45.8** (515K) | Fits on 1 card; both hidden facts exact |

### Multi-Card Split & Shared-Cache Performance (Host-Staged, 0 Card Faults)

| Topology | 3K / 31K Prompt | 100K Prompt | 200K Prompt | 200K Decode (Shared) | 1M Needle Prompt | 1M Decode Plain | 1M Decode DSpark |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 cards (`0–1` / `1+2`) | **2,233 / 2,838** (`+22/+13%`) | 1,962 tok/s (1.89×) | 1,425 tok/s (1.99×) | 51.9 plain / 77.8 DSpark | 400.9 tok/s | 12.56 (19.37 first 200) | **33.97 tok/s** |
| 4 cards (`0–3` / `1–4`) | **3,052 / 4,623** (`+74/+38%`) | **3,709 tok/s** (`+3.1%`) | 2,786 tok/s (3.83×) | 59.4 plain / 84.9 DSpark | 795.7 tok/s | 16.01 (28.18 first 200) | **48.18 tok/s** |
| 5 cards (`1–5`) | — | 3,857 tok/s (3.70×) | **3,076 tok/s** | **58.9 plain** (`59.4` P=3) / **89.3 DSpark** (`+5.6/+3.8%`) | 812.8 tok/s | 16.64 (34.78 first 200) | **62.29 tok/s** |
| 6 cards (`0–5`, cuts `7,15,23,30,37`) | **3,149 / 5,997** (`+89/+71%`) | **4,793.8** plain / **4,568.2** DSpark (`+3.6%`) | **3,443.0** plain / **3,390.8** DSpark (`+1.7%`) | **62.0 plain / 91.2 DSpark** (`f8cb2ae7e0`) | **891.6 tok/s** (**+9.7%** vs 5c) | — | **68.59 tok/s** (**+10.1%** vs 5c) |

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
  - **Open single-card prompt experiment (issue #87, untested here).** For a 1,024-token append at 32K and 128K depth, test whether assigning 128-key blocks of full attention to more workers pays for writing partial results and folding them. Use the current fused prompt tile as control, keep the FP32 block arithmetic and ascending fold, and compare logits, total append time and joules. The existing block-parts path is an exactness reference. The earlier three-part XMX score trial is already closed. [Contributor’s split control and test details](../../../community/ljedrz-inkling2-sycl/STATUS.md#experiments-worth-screening)
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
