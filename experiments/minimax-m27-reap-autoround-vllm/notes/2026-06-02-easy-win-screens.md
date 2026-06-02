# 2026-06-02 Easy-Win Screens

Goal: continue looking for quality-preserving REAP decode improvements after the
current live-source quality-safe lane fell back to the low-83 output tok/s band.

## Tooling

Extended experiment metadata/passthrough so future runs preserve and record the
newer low-level toggles:

- `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE`
- `VLLM_MINIMAX_QK_NORM_PRECAPTURE_SANITIZE`
- `VLLM_MINIMAX_QK_NORM_PRECAPTURE_USE_PARAM`
- `VLLM_MINIMAX_QKV_NARROW_SPLIT`
- `VLLM_MINIMAX_M2_FP16_ROUTER`
- `VLLM_MINIMAX_M2_FP16_ROUTER_AUDIT`
- `VLLM_XPU_STATIC_PIECEWISE_RANGE_ENTRY`

Also added `--enforce-eager` to `scripts/async-quality-smoke.py` so router audit
work can run outside Dynamo graph capture.

## Results

### QKV narrow split

Settings:

- `VLLM_MINIMAX_QKV_NARROW_SPLIT=1`
- restore-weight off
- full-forward MoE custom op off
- attention-delay allreduce on

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-narrow-split-20260602T025047Z.json`
- passed
- `384` generated tokens
- `173` distinct generated token IDs
- no NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T025506Z.json`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T025506Z.log`
- total throughput: `110.94842893833007 tok/s`
- output throughput: `83.21 tok/s`

Decision: reject as neutral. It is quality-clean but does not improve over the
current `83.52` quality-safe baseline.

### FP16 router

Audit first ran in eager mode because compiling the audit print path caused a
Dynamo data-dependent expression failure.

Audit:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fp16-router-eager-audit-20260602T025942Z.json`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fp16-router-eager-audit-20260602T025942Z.log`
- quality passed
- audit lines: `496`
- expert-set mismatches: `0`
- top-12/top-16/top-32 candidate misses: `0`
- ordered-only mismatches: `8`, all in decode layers `21` and `37`

Compiled quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fp16-router-20260602T030203Z.json`
- passed
- `384` generated tokens
- `179` distinct generated token IDs
- no NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T030623Z.json`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T030623Z.log`
- total throughput: `112.15304870538034 tok/s`
- output throughput: `84.11 tok/s`

Decision: candidate only, not a conservative promotion. This is the best new
fresh-cache speed from this pass, but it changes router numerical behavior. The
active expert set stayed stable in the smoke audit, while top-k order changed in
two decode layers.

### Q/K helper installed and active

The active vLLM env initially could not import `minimax_qk_rms_xpu`, so
`VLLM_MINIMAX_QK_RMS_XPU_HELPER=1` was effectively a no-op in offline runs.

Install attempt:

```bash
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
set -u
source /home/steve/.venvs/vllm-xpu/bin/activate
export CC=icx
export CXX=icpx
export MINIMAX_QK_RMS_XPU_SYCL_DEVICE=bmg
python -m pip install --no-build-isolation -e \
  /home/steve/llm-optimizations/experiments/minimax_qk_rms_xpu
```

The first build failed under pip build isolation because `torch` was hidden. The
second failed with plain `c++` because it did not support `-fsycl`. The `icpx`
build succeeded and registered:

- `minimax_qk_rms_xpu::var_alloc`
- `minimax_qk_rms_xpu::apply_alloc`
- `minimax_qk_rms_xpu::apply_f32_weight_alloc`

It did not expose the scaled apply variants, so the tested config kept
`VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE=0`.

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-qk-helper-active-20260602T031128Z.json`
- passed
- `384` generated tokens
- `169` distinct generated token IDs
- no NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T031520Z.json`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T031520Z.log`
- total throughput: `109.71972673105371 tok/s`
- output throughput: `82.29 tok/s`

Decision: reject. The helper is now buildable and quality-clean, but the active
helper path is slower than both the current baseline and the FP16-router
candidate.

### Pre-capture sanitizer and static range screens

Pre-capture Q/K norm sanitizer:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-precapture-restore1-qk1-fullforward0-20260602T022930Z.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T023355Z.json`
- output throughput: `83.10 tok/s`
- decision: quality-clean but no speed improvement

Static PIECEWISE widest-entry policy:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-static-widest-restore0-qk1-fullforward0-20260602T023921Z.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T024345Z.json`
- output throughput: `81.12 tok/s`
- decision: reject

## Current State

Conservative quality-safe best remains:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`
- `83.517837` output tok/s
- no router precision change

Best new speed candidate:

- FP16 router
- `84.11` output tok/s
- quality smoke passed and expert-set audit stayed stable, but router numerical
  behavior is not exact, so keep it opt-in.

Do not submit a LocalMaxxing update from these runs. The archived
`89.49922316987691` output tok/s record is still higher, and the new
quality-clean screens do not beat it.

## Next Work

The easy screens are exhausted. Sizeable quality-preserving improvement likely
requires source work in one of these areas:

- restore-weight-safe Q/K RMS graph path that avoids the stale fast-cache
  corruption without falling back to the low-83 graph shape
- lower-level Q/K allreduce plus RMS fusion rather than the standalone helper
- E=192 MiniMax MoE/logits workspace path that passes fresh-cache async quality
  and beats the conservative path
- deeper MoE expert/epilogue scheduling work, because `experts_total` remains
  the largest measured decode bucket
