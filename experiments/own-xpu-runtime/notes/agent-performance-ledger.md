# Multi-Agent Performance Ledger (Opus 5.5 + Kimi 3.1 Pro + Codex GPT-6.2-Astra)

Living empirical tracker of agent strengths, weaknesses, hit rates, turnaround times, and failure modes across `experiments/own-xpu-runtime/` (starting with Inkling-2-Mini on 6× Intel Arc Pro B70, expanding to DeepSeek V4.1, Qwen Flash, and future custom-engine lanes).

**Orchestration model:** Coordinator (Gemini) owns git state, `icpx` builds (1 at a time on 15 GiB RAM), 6-card GPU waves (`run-wave.sh` on cards `0–5`), exactness gates (`check-fast.sh` → `check-exact.sh`), `SCOREBOARD.md`, `DO-NOT-REPEAT.md`, and GitHub/neural.download updates. Specialist agents get fresh, scoped, non-blocking tasks matched to their measured strengths.

---

## Baseline Empirical Profiles (from 40-Day Audit: 2026-10-18 – 2026-11-27)

| Agent / Model | Verified Strengths | Verified Failure Modes to Guard Against | Assigned Primary Role |
|---|---|---|---|
| **Claude Opus 5.5** (`claude-opus-5-5`) | Deep SYCL/ESIMD/XMX kernel authoring from scratch; exact DPAS/BF16-split matrix engines; 623 commits (Inkling2 `19.6 → 90/134 tok/s` decode, `72 → 1,889 tok/s` prompt; DeepSeek `9 → 111/165 tok/s`). | Self-imposed guardrails (banned card 0 for 4 days; gated 2-card runs for 11.5 h); `AskUserQuestion` halts (2.47 h); marathon session drift; occasional trial-and-error before profiling. | **Kernel & Compiler Specialist** — fresh scoped turns to write hard SYCL/ESIMD/XMX kernel patches into isolated diff/patch files; never owns GPU scheduling or approval decisions. |
| **OMP / Kimi 3.1 Pro** (`kimi-code/k3.1-pro:max`) | Disciplined execution without fake gates; immediately ran 2/4/5/6-card + 1M needles (0 faults); fast 6-way parallel sweeps (276 s); strong speculative/controller tuning (`+8.0–8.5%` long-context DSpark). | Earlier bring-up stalled on 15 GiB host-RAM OOMs before per-card SYCL context fix; less proven authoring brand-new ESIMD/DPAS kernels from scratch. | **Policy, Scheduling, Parallel-Sweep & Architecture Specialist** — DSpark/adaptive controllers, host-staging/pipeline/serving improvements, reusable cross-model engine abstractions, and competing kernel prototypes. |
| **Codex GPT-6.2-Astra** (`gpt-6.2-astra`) | Skeptical mathematical floor audits & code review; caught Opus's false *"at its floor"* claim (Nov 13); strong race/exactness analysis and hardware/OS triage. | Silent turn-end stops (9 h 18 m on Oct 23); conservative stability holds; factual slip on public TP4 copy (Nov 12); firmware packaging bug (Nov 18). | **Chief Skeptic, Bottleneck Ranker & Pre-GPU Code Reviewer** — read-only profile/ISA/floor analysis, bit-exactness/race review of candidate patches before compile/GPU spend, and challenging "we hit the floor" claims. |

---

## Orchestrated Round Log

| Round | Date | Target Lane / Metric | Codex Astra 6.2 (Plan / Review) | Opus 5.5 (Kernel Patch) | Kimi 3.1 Pro (Policy / Alt Patch) | Measured Result (Bit-Exact Gate) | Observed Agent Notes |
|---|---|---|---|---|---|---|---|
| *Init* | 2026-11-27 | Inkling-2-Mini (v8 + `e25b20a655`) | *Pending R1* | *Pending R1* | *Pending R1* | Baseline: short 88.85/140.7, 3K prompt 1,889, 100K/200K DSpark 53.19/98.35 | Ledger created; `AGENTS.md`, `DO-NOT-REPEAT.md`, `check-fast.sh`, `run-wave.sh`, `common/` live. |
| **R1** | 2026-11-27 | Inkling-2-Mini single-card decode + 200K DSpark | **Plan (307 s):** Ranked top 3 bit-exact levers (`XProd2` remainder tiles, `XFull` K-panel layout, `attn_flash_dec` exact rows +0.8–1.8%). **Reviews (93 s & 85 s):** Caught Opus's hidden `pre0`/`pre1` shared-spill hazard AND caught Kimi's `nt==1` `VAR=1` regression before GPU burn. | **Kernel patch (578 s):** Folded 48 `ctl_norm` launches into `mix_fused_v<12>` (`791 → 743` launches). Clean patch, zero guardrails, passed `check-fast.sh` first try — **but spilled 35 GRFs**, regressing **−8.5%** (`89.0 → 81.5` plain, `142.8 → 135.9` DSpark). Reverted & logged. | **Dispatch patch + wave (1,292 s):** Specialized `attn_flash_dec<3,NT,1>` for exact `NT=2,3,5,6,7` across normal/chunked/shared paths + designed balanced 12-arm 6-card 200K wave. Minor `nt==1` `VAR=1` bug fixed via Codex review. | **PROMOTED (Kimi R1 + Codex fix):** 6/6 cards won on 200K DSpark (**+1.14% to +1.54%, mean +1.38%**), 12/12 EXACT IDs, 0 GPU faults, 15/15 `check-exact.sh` PASS, 5/5 forced-width `NT=2,3,5,6,7` logits bit-identical, short decode neutral (`89.25 → 89.14`). | **Codex:** S-tier pre-GPU reviewer & floor ranker (2/2 critical catches in <95 s each; +0.8–1.8% prediction nailed actual +1.38%). **Opus:** Fast, clean, exact codegen, zero guardrails, but missed 128-GRF spill cliff on `mix_fused_v`. **Kimi:** Slower turnaround (21.5 m), solid dispatch + 6-card wave design, needs Codex pre-build edge-case check (`nt==1`). |

---

## Running Lessons for Cross-Model Engine Reuse

Track every technique that generalizes beyond Inkling-2-Mini to DeepSeek V4.1, Qwen Flash, and future B70 engines:
1. **Exact BF16-split DPAS on Xe2 XMX** (Opus): 3-part BF16 split for exact FP32 matrix products on XMX — transfers directly to any Q8_0/Q6_K/NVFP4/INT4 linear/MoE layer on B70.
2. **Online calibrated speculative stopping + plain-streak skip** (Kimi): `INK_SPEC_PLAIN_SKIP` + per-bucket online calibration — architecture-independent, transfers directly to DeepSeek MTP / Qwen MTP / DFlash / Eagle.
3. **One `sycl::context(dev)` per card + `free_memory` pre-check** (Opus): mandatory on 15 GiB hosts with `xe` driver to prevent TTM host-RAM eviction freezes.
4. **6-card parallel wave sweeps** (`scripts/run-wave.sh`, Kimi/Coordinator): run 6 independent single-card trials simultaneously rather than serializing sweeps on 1 card.
5. **Exact-width speculative target attention** (`NT=2,3,5,6,7`, `9485a273ed`, Codex plan + Kimi patch + Codex `nt==1` review): dispatch speculative verification attention by actual live check-row count instead of padding into 4/8-row masked kernels — transfers directly to DeepSeek V4.1 MTP, Qwen Flash MTP/DFlash, and Eagle speculative verifiers.
