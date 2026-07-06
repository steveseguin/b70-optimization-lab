# ReplaySSM commit-pending active-slot guard

Date: 2026-07-06

Model lane: `webhie/Qwen3.6-27B-int4-AutoRound` on Intel Arc Pro B70, current best strict fresh-response result still `68.23626314761921 tok/s`.

## Why this mattered

The next credible path toward >100 tok/s is not more config roulette. We need graph-safe partial-group / branch-regenerate mechanics for GDN/DeltaNet state, which means the ReplaySSM state transaction primitives must have a clean contract for invalid, null, and inactive rows.

`torch.ops._xpu_C.gdn_replayssm_commit_pending` did not have that contract: a guard case containing null slot 0, out-of-range slots, inactive rows, and accepted counts beyond `pending_len` showed metadata mutations where the Python reference expected no-op behavior:

- `write_pos`: mismatch;
- `is_flush`: mismatch;
- `pending`: mismatch;
- `conv_state` / `cache_base`: matched in the first failing case, but metadata corruption alone is enough to poison later state transitions.

This is infrastructure work, not a headline throughput win and not a LocalMaxxing submission.

## Fix

Added a standalone guard:

- `/home/steve/llm-optimizations/scripts/check-gdn-replayssm-commit-pending.py`

The guard launches the native op outside vLLM and compares against a Python reference. It intentionally includes:

- null slot `0`;
- negative and out-of-range state indices;
- inactive rows where `pending[slot] == 0`;
- accepted counts below zero and beyond `pending_len`;
- flush and non-flush cursor paths;
- conv-state tails outside the active causal window.

Source patch records:

- `/home/steve/llm-optimizations/patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-commit-pending-fallback-active-slot-guard-20260706.patch`
- `/home/steve/llm-optimizations/patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-replayssm-commit-pending-active-slot-guard-20260706.patch`

The Python fallback now filters to valid slots first, then filters active `pending != 0` rows, and returns without touching any state if the request set is empty after filtering.

The native kernel now:

- maps invalid, null, or out-of-range rows to slot 0 only as a safe placeholder;
- checks `active_for_row(row, slot)` before reading/writing state;
- returns early for inactive rows, so cursor metadata is no-op for null/out-of-range/inactive entries;
- keeps the old per-element launch shape to avoid changing the working kernel shape while tightening the contract.

## Build environment lesson

Do not rebuild these kernels with umbrella `/opt/intel/oneapi/setvars.sh` for this runtime. That selected the 2026 compiler stack and produced `_xpu_C.abi3.so` linked against `libsycl.so.9`, while the vLLM-XPU runtime uses the 2025.3-era venv libraries (`libsycl.so.8`). The mismatch produced import/teardown instability and made native crash/hang results uninterpretable.

Working build path for this lane:

```bash
cd /home/steve/src/vllm-xpu-kernels
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
set -u
cmake --build build/temp -j=24 --target=_xpu_C
cp build/temp/_xpu_C.abi3.so vllm_xpu_kernels/_xpu_C.abi3.so
cp build/temp/libgdn_attn_kernels_xe_2.so vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so
cp build/temp/libgrouped_gemm_xe_2.so vllm_xpu_kernels/libgrouped_gemm_xe_2.so
cp build/temp/libgrouped_gemm_xe_default.so vllm_xpu_kernels/libgrouped_gemm_xe_default.so
cp build/temp/libmqa_logits_kernels_xe_2.so vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so
```

Runtime check after rebuild:

```bash
LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib" \
ldd /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so | grep -E 'libsycl|libimf|libintlc|not found'
```

Expected key result: `libsycl.so.8` from `/home/steve/.venvs/vllm-xpu/lib`, no `libsycl.so.9`.

## Validation

Common runtime prefix:

```bash
cd /home/steve/llm-optimizations
export VLLM_TARGET_DEVICE=xpu
export PYTHONPATH=/home/steve/src/vllm-xpu-kernels:/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}
export LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
PY=/home/steve/.venvs/vllm-xpu/bin/python
```

Commands run:

```bash
$PY -m py_compile scripts/check-gdn-replayssm-commit-pending.py
timeout 20s $PY scripts/check-gdn-replayssm-commit-pending.py --device xpu:0 --dtype bf16 --rows 0 --conv-dim 1 --json-out /tmp/gdn-commit-zero-after-2025.json
timeout 20s $PY scripts/check-gdn-replayssm-commit-pending.py --device xpu:0 --dtype bf16 --rows 1 --conv-dim 1 --json-out /tmp/gdn-commit-null-after-2025.json
timeout 30s $PY scripts/check-gdn-replayssm-commit-pending.py --device xpu:0 --dtype bf16 --json-out /tmp/gdn-replayssm-commit-pending-bf16-after.json
timeout 30s $PY scripts/check-gdn-replayssm-commit-pending.py --device xpu:0 --dtype fp16 --json-out /tmp/gdn-replayssm-commit-pending-fp16-after.json
timeout 30s $PY scripts/check-gdn-replayssm-commit-pending.py --device xpu:0 --dtype fp32 --json-out /tmp/gdn-replayssm-commit-pending-fp32-after.json
timeout 60s $PY scripts/check-gdn-native-spec-prefix.py --device xpu:0 --spec-len 3 --json-out /tmp/gdn-native-prefix-check-s3-after-commitfix.json
timeout 60s $PY scripts/check-gdn-spec-recurrent-exact.py --spec-len 3
```

Results:

- zero-row guard: pass;
- one-row null-slot guard: pass;
- full BF16 guard: pass, all equality fields true, max diffs zero;
- full FP16 guard: pass, all equality fields true, max diffs zero;
- full FP32 guard: pass, all equality fields true, max diffs zero;
- native spec-prefix check: pass;
- recurrent exact endpoint scheduler cases: pass.

Tracked diagnostic outputs:

- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-commit-pending-zero-bf16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-commit-pending-null-bf16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-commit-pending-full-bf16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-commit-pending-full-fp16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-commit-pending-full-fp32-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-native-prefix-check-s3-after-commitfix-20260706.json`

## Status and next action

This closes a real native ReplaySSM contract bug and gives us a reusable guard for later branch-regenerate work. It does not change the current endpoint record and should not be submitted as a benchmark result.

Next implementation step: use this guarded transaction primitive while prototyping graph-safe partial-group / branch-regenerate, then validate on strict fresh-response Qwen27 only if endpoint behavior becomes correct and faster than `68.23626314761921 tok/s`.
