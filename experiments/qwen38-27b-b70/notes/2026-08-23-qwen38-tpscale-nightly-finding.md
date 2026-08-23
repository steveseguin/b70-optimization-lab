# TP scaling on the containerized XPU nightly: eager is flat, XPU graph scales - 71.7 tok/s target-only at TP4

Date: 2026-08-23. Extends the
[TP1 nightly bring-up](2026-08-22-qwen38-tp1-vllm-nightly-bringup-finding.md)
to TP2/TP3/TP4 per the "primary combos" request.
Data: [`2026-08-23-qwen38-tpscale-nightly-matrix.json`](../data/2026-08-23-qwen38-tpscale-nightly-matrix.json).
Raw runs: `bench-results/.../tp1-nightly-20260822/tp{2,4}-*`. Same driver,
suite, conventional metric, and cache-zero gates as the TP1 matrix; MTP off,
f16 KV, `--max-num-seqs 1`.

## The map (conventional decode tok/s, single stream)

| TP (cards) | eager | XPU graph ON | prefill (either) | TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 23.7 / 24.2 | 30.2 / 30.3 | 281 | 0.27 s |
| 2 (GPUs 2,3) | 16.8 | **48.8** | ~500 | 0.15 s |
| 3 | impossible | impossible | - | - |
| 4 (all) | 17.4 | **71.7** | ~860 | 0.09 s |

1. **Eager multi-GPU decode is flat**: TP2 and TP4 both land at ~17 tok/s,
   BELOW single-card (24). The container's per-decode-step collective cost
   (oneCCL with `CCL_ZE_IPC_EXCHANGE=sockets`) swallows the parallelism.
   Prefill still scales (281 -> ~500 -> ~860 tok/s) and TTFT improves
   (0.27 -> 0.09 s): the tax is per-step latency, not bandwidth.
2. **`VLLM_XPU_ENABLE_XPU_GRAPH=1` (nightly default OFF) restores decode
   scaling**: 30.2 -> 48.8 -> 71.7 at TP1 -> 2 -> 4. Graph capture folds the
   per-step launch/collective orchestration out of the critical path.
   **71.7 tok/s is the fastest target-only conventional decode the lab has
   measured on any lane** (promoted llama.cpp TP2 target-only: 50.2).
3. **TP3 is architecturally impossible** for Qwen3.8-27B: 16 GDN K heads are
   not divisible by 3 (worker init assertion). Valid TP sizes: 1, 2, 4.
4. **TP4 needs `gpu-memory-utilization <= ~0.6`** on 32 GiB cards: at 0.90
   the KV region becomes a single ~20 GiB allocation that trips the XPU
   per-allocation cap ("Tried to allocate 20.13 GiB ... 24.66 GiB is free").
   The driver takes `GPU_MEM_UTIL` env now. For `--max-num-seqs 1` at 32K
   the KV need is only a few GiB, so nothing is lost.
5. **Device-selection trap**: do not combine `ONEAPI_DEVICE_SELECTOR` with
   `ZE_AFFINITY_MASK` for GPU subsets - the mask renumbers devices and the
   selector then filters the renumbered list, so any list that is not a
   `0..k` prefix yields "No XPU devices available". The driver now sets only
   `ZE_AFFINITY_MASK`.

## Status and caveats

**TP4-graph is certified (2026-08-23):** full quality battery pass on the
exact config (code canary `14`, arithmetic/factual/logic/JSON/copy exact,
8-run repeat stability, 8K needle, `baseline_match_all`) and a repeat boot
at **71.5488** (pair 71.67 / 71.55, 0.17% spread). **TP2-graph is also
battery-certified** (2026-08-23, pass_all on the exact config), so the whole
graph column 30.2 / 48.8 / 71.7 carries a quality battery pass. The lane's
cross-boot nondeterminism caveat (autotune) applies to all configs, so no
cross-boot token-exactness claim.

**MTP at TP4: does not boot.** The probe arm (MTP2, eager, util 0.60) hung
at worker init - all ranks repeating the shm_broadcast "No available shared
memory broadcast block ... processes hanging" starvation message until the
health timeout killed it (root `tp4-mtp2-f16-a`). Spec decode at TP>1 on
this container stack is unavailable pending an upstream fix, so the TP1
verify-step question stays TP1-scoped and 71.7 target-only is the multi-card
ceiling for now.
