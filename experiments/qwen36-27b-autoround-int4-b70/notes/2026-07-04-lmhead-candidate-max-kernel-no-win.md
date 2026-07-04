# 2026-07-04 - Qwen27 LM-head Candidate-Max Kernel No-Win

## Summary

The native full-vocab `int8_lm_head_candidate_max_w8a8` prototype is exact
against dense logits, but it does **not** meet the integration speed gate. It
keeps the correct semantics needed for target-verified speculation:

- true top token ID/value for every verifier/draft row;
- per-row draft candidate score;
- `candidate_is_top` flag;
- BF16 LM-head scales;
- rows `1,2,3,4`, hidden `5120`, vocab `248320`.

The measured result is effectively the same as the previous compact top-1
attempt: the expensive part is still the full-vocab scan plus cross-tile
reduction, and candidate-score extraction does not change that cost model.

## Artifacts

- patch:
  `../../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lmhead-candidate-max-no-win-20260704.patch`
- diagnostic result:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-candidate-max-bf16scale-microbench-20260704.json`
- harness:
  `../../../scripts/bench-int8-lm-head-candidate-max.py`
- temp build source used during the run:
  `/tmp/vllm-xpu-kernels-lmhead-candidate-20260704`

The temp source was intentionally separate from
`/home/steve/src/vllm-xpu-kernels`, which still contains unrelated dirty
Qwen35/GDN/MoE work. Do not edit the dirty kernel tree in-place for this lane.

## Build Notes

The first isolated configure selected `/opt/intel/oneapi/compiler/latest`
SYCL, which currently resolves to the 2026 runtime. That produced a load
failure with the active Torch/vLLM 2025.3 runtime:

```text
OSError: /opt/intel/oneapi/compiler/latest/lib/libsycl.so.9:
undefined symbol: urDeviceWaitExp, version LIBUR_LOADER_0.12
```

Forcing the 2026 runtime library order segfaulted immediately. The working
build explicitly pinned the 2025.3 compiler and SYCL paths:

```bash
/home/steve/.local/share/uv/tools/cmake/bin/cmake \
  -S /tmp/vllm-xpu-kernels-lmhead-candidate-20260704 \
  -B /tmp/vllm-xpu-kernels-lmhead-candidate-20260704/build/xpu-c-candidate-20260704 \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2025.3/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2025.3/bin/icpx \
  -DCMAKE_ASM_COMPILER=/opt/intel/oneapi/compiler/2025.3/bin/icx \
  -DSYCL_INCLUDE_DIR=/opt/intel/oneapi/compiler/2025.3/include \
  -DSYCL_INCLUDE_SYCL_DIR=/opt/intel/oneapi/compiler/2025.3/include/sycl \
  -DSYCL_LIBRARY=/opt/intel/oneapi/compiler/2025.3/lib/libsycl.so \
  -DSYCL_LIBRARY_DIR=/opt/intel/oneapi/compiler/2025.3/lib \
  -DVLLM_TARGET_DEVICE=xpu \
  -DXPU_SPECIFIC_KERNELS_ENABLED=ON \
  -DBASIC_KERNELS_ENABLED=OFF \
  -DBUILD_SYCL_TLA_KERNELS=ON \
  -DVLLM_XPU_ENABLE_XE2=ON \
  -DVLLM_XPU_ENABLE_XE_DEFAULT=OFF \
  -DVLLM_PYTHON_EXECUTABLE=/home/steve/.venvs/vllm-xpu/bin/python \
  -DTorch_DIR=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/share/cmake/Torch \
  -DDPCPP_SYCL_TARGET=intel_gpu_bmg_g21
```

Build target:

```bash
/home/steve/.local/share/uv/tools/cmake/bin/cmake \
  --build /tmp/vllm-xpu-kernels-lmhead-candidate-20260704/build/xpu-c-candidate-20260704 \
  --target _xpu_C -j 8
```

Run command:

```bash
ZE_AFFINITY_MASK=0 \
LD_LIBRARY_PATH=/tmp/vllm-xpu-kernels-lmhead-candidate-20260704/build/xpu-c-candidate-20260704:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-int8-lm-head-candidate-max.py \
  --xpu-so /tmp/vllm-xpu-kernels-lmhead-candidate-20260704/build/xpu-c-candidate-20260704/_xpu_C.abi3.so \
  --device xpu:0 \
  --rows 1,2,3,4 \
  --scale-dtype bf16 \
  --warmup 3 \
  --repeats 10 \
  --out data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-candidate-max-bf16scale-microbench-20260704.json
```

## Results

All rows were exact: `top_id_mismatches_vs_baseline=0`,
`candidate_is_top_mismatches=0`, `max_top_value_abs_diff=0.0`, and
`max_candidate_value_abs_diff=0.0`.

| Rows | Dense baseline median ms | Candidate-max median ms | Speedup |
| ---: | ---: | ---: | ---: |
| 1 | 2.6962 | 2.6683 | 1.0105x |
| 2 | 2.6332 | 2.6749 | 0.9844x |
| 3 | 2.5969 | 2.6738 | 0.9712x |
| 4 | 2.5704 | 2.6743 | 0.9611x |

Promotion rule was `<2.3 ms` or `>1.10x` over dense rows `1-4`. This
prototype fails that rule.

## Decision

Do **not** wire `int8_lm_head_candidate_max_w8a8` into vLLM. It is exact, but
too close to / slower than dense oneDNN plus argmax, and endpoint overhead would
erase the tiny rows-1 win.

The full-vocab standalone native reduction lane is now closed twice:

1. compact top-1 no-win:
   `2026-07-04-compact-lmhead-top1-kernel-no-win.md`;
2. candidate-max no-win: this note.

The next Qwen27 work should not be another standalone full-vocab top-1 kernel
with a second reduction launch. Credible follow-ups are:

- oneDNN/XPU-integrated top-ID/candidate-score post-op or epilogue, if a real
  hook exists upstream or can be added without a second full reduction launch;
- reduce LM-head calls/rows before the GEMM, but only where target replacement
  and bonus semantics remain exact;
- target-matched drafter work using held-out calibration traces, because
  improving accepted tokens per verifier step remains the larger path to
  `90-100 tok/s`.

This is diagnostic-only. It is not a LocalMaxxing result and does not change
the current valid record (`65.27648650325429 tok/s`).
