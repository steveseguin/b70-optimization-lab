# 2026-06-02 Profile, Output-Reuse, And Cache-Op Follow-Up

Goal: continue REAP MiniMax M2.7 INT4 AutoRound decode optimization after the
quality-clean logits-WS lane reached the mid-80 output tok/s band, and check
whether small source/runtime changes can recover the archived `89.499223`
output tok/s record.

## Baseline Recheck

Accepted baseline settings:

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
- `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
- `VLLM_XPU_SKIP_COMPILED_PREFILL=1`
- `VLLM_BENCH_TEMPERATURE=0`
- `CCL_IPC=pidfd`, `CCL_ZE_IPC_EXCHANGE=pidfd`
- `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`
- cache: `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-default-qk0-20260602T034639Z`

After rebuilding `moe_int4_ops` with the one-op BMG build helper, the accepted
lane still works:

- quality source: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-default-qk0-20260602T034639Z.json`
- rerun benchmark: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125056Z.log`
- result: `113.61` total tok/s, `85.21` output tok/s

Decision: keep this as the current live-source quality-clean best from this
pass. It is still below the archived `89.499223` output tok/s record.

## Profiles And Rejected Q/K Helper Variant

Short timing profiles at `p512/n256` showed the largest measured decode bucket
is still MiniMax MoE expert work:

- logits-WS default/qk0:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/logitsws-default-qk0-20260602/vllm-minimax-m27-autoround-tp4-p512n256-20260602T121706Z.log`
  - `80.60` output tok/s for the short profile shape
  - `minimax.moe.experts_total`: `4.510390 ms` avg
  - `minimax.attn.qk_norm`: `1.742430 ms` avg
- regular WS/down4/qk0:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/regular-ws-downhtile4-qk0-20260602/vllm-minimax-m27-autoround-tp4-p512n256-20260602T121843Z.log`
  - `79.54` output tok/s for the short profile shape
  - `minimax.moe.experts_total`: `4.273121 ms` avg
  - `minimax.attn.qk_norm`: `1.843607 ms` avg

The preserved `f728d2c0cf` fast-cache profile attempt failed under current
timing/current command shape with an AOT tuple mismatch:

- `ValueError: not enough values to unpack (expected 811, got 749)`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/f728-throughput-control-20260602/vllm-minimax-m27-autoround-tp4-p512n256-20260602T122035Z.log`

Q/K post-allreduce helper screen:

- env added:
  - `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
  - `VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP=1`
  - `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1`
  - `VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE=0`
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-qkhelper-postar-20260602T122344Z.json`
  - passed, `384` generated tokens, `185` distinct generated token IDs, no
    NUL/control output
- profile:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/logitsws-qkhelper-postar-20260602/vllm-minimax-m27-autoround-tp4-p512n256-20260602T122728Z.log`
  - `77.89` output tok/s for the short profile shape

Decision: reject the Q/K post-allreduce helper path.

## Output-Reuse Source Experiment

Patch archived:

- `patches/llm-scaler-minimax-ws-output-reuse-experiment-20260602.patch`

Build:

```bash
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
set -u
source /home/steve/.venvs/vllm-xpu/bin/activate
export CC=icx
export CXX=icpx
export SYCL_CACHE_PERSISTENT=1
export TORCH_XPU_ARCH_LIST=bmg
python setup_moe_int4_only.py build_ext --inplace
```

The one-op BMG build succeeded and copied:

- `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python/custom_esimd_kernels_vllm/moe_int4_ops.cpython-312-x86_64-linux-gnu.so`
- size after build: `97M`

Microbench with `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES=1`:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/micro/moe-e192-logitsws-reuse-output-tokens1-20260602T123912Z.json`
- `minimax_logits_ws` median: `0.061245 ms`
- max absolute diff vs routed U4 for `minimax_logits_ws`: `9.5367431640625e-07`

The microbench looked safe, but full decode did not improve.

First output-reuse full-model run accidentally used `FULL_FORWARD_CUSTOM_OP=1`
from the promoted env:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-reuse-output-qk0-20260602T124011Z.json`
  - passed, `384` generated tokens, `185` distinct generated token IDs, no
    NUL/control output
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T124424Z.log`
  - `108.57` total tok/s
  - `81.42` output tok/s

Corrected output-reuse run with the accepted `FULL_FORWARD_CUSTOM_OP=0` settings:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-outputreuse-fullforward0-qk0-20260602T125935Z.json`
  - passed, `384` generated tokens, `187` distinct generated token IDs, no
    NUL/control output
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T130101Z.log`
  - `113.24` total tok/s
  - `84.93` output tok/s

Decision: reject output reuse. It is quality-clean, but it is slower than the
same-cache accepted baseline (`85.21` output tok/s). Keep the flag default-off
only as a diagnostic reference.

## Cached MiniMax Logits Op

Retested `VLLM_XPU_LLM_SCALER_MOE_CACHE_MINIMAX_LOGITS_OP=1` under the corrected
restore-off/qk0/full-forward-off settings, because an earlier cached-op attempt
failed in a mixed restore-weight context.

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-cacheop-restore0-qk0-fullforward0-20260602T125318Z.json`
- passed, `384` generated tokens, `183` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125738Z.log`
- `112.85` total tok/s
- `84.64` output tok/s

Decision: reject. It is quality-clean but slower than the accepted baseline.

## Current State

Current quality-clean live-source best:

- settings: logits-WS, skip redundant contiguous, qk helper off, restore off,
  attention-delay allreduce on, full-forward MoE custom op off
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-default-qk0-20260602T034639Z.json`
- best fresh rerun after rebuild:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125056Z.log`
- result: `85.21` output tok/s, `113.61` total tok/s

No new LocalMaxxing submission is warranted. The best submitted REAP result is
still the archived `89.499223` output tok/s pidfd run, and today's quality-clean
source/runtime screens do not beat it.

## Next Work

The cheap allocator and Python lookup experiments are exhausted. The profile
still points at MoE experts and Q/K normalization/allreduce as the meaningful
targets.

Potential next source work:

- add lower-overhead timing inside the WS up/down kernels to split
  `experts_total` into up, down, top-k, and queue/launch cost without perturbing
  AOT cache shape too much
- investigate fusing or retiming Q/K RMS plus allreduce instead of the current
  standalone helper, which was quality-clean but slower
- inspect the WS down kernel for H-tile/vectorization pressure on BMG and compare
  register spill/occupancy for H_TILE=4 versus H_TILE=8 in IGC output
- keep old `f728d2c0cf` only as a throughput/corruption reference; it cannot be
  promoted unless quality is repaired without losing the speed
