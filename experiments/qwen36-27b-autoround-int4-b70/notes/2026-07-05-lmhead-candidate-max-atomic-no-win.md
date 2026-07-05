# 2026-07-05 - Qwen27 LM-head Candidate-Max Atomic Kernel No-Win

## Summary

Followed through on the custom-kernel route for the Qwen27 `100+ tok/s` goal:
the prior candidate-max kernel was exact but still paid a second partial-result
reduction launch. This experiment removed that reducer by packing each tile's
top score/token into a monotonic `uint64_t` key and using a device-scope atomic
max into one row key, followed by a tiny decode kernel.

The result is exact, but still slower than dense oneDNN logits for the real
Qwen27 LM-head shape. Do **not** wire this op into vLLM.

This is not backing away from the `100+ tok/s` target; it closes one concrete
low-level hypothesis. A standalone full-vocab top-token/candidate scan is not
the path. The next implementation work has to remove whole verifier/LM-head
calls or materially increase accepted tokens per target pass.

## Artifacts

- patch snapshot:
  `../../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lmhead-candidate-max-atomic-no-win-20260705.patch`
- harness diff:
  `../../../patches/qwen36-27b-autoround-int4-b70/bench-int8-lm-head-candidate-max-atomic-harness-20260705.patch`
- diagnostic result:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-candidate-max-atomic-bf16scale-microbench-20260705.json`
- active build artifact used for the run:
  `/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025/_xpu_C.abi3.so`

## Build And Run

Build:

```bash
cd /home/steve/src/vllm-xpu-kernels
/home/steve/.local/share/uv/tools/cmake/bin/cmake \
  --build build/xpu-c-only-2025 --target _xpu_C -j 8
```

Run:

```bash
cd /home/steve/llm-optimizations
ZE_AFFINITY_MASK=0 \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-int8-lm-head-candidate-max.py \
  --xpu-so /home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025/_xpu_C.abi3.so \
  --device xpu:0 \
  --rows 1,2,3,4 \
  --scale-dtype bf16 \
  --warmup 3 \
  --repeats 10 \
  --out data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-candidate-max-atomic-bf16scale-microbench-20260705.json
```

## Result

All rows were exact against the dense baseline:
`atomic_top_id_mismatches_vs_baseline=0`,
`atomic_candidate_is_top_mismatches=0`, `atomic_max_top_value_abs_diff=0.0`,
and `atomic_max_candidate_value_abs_diff=0.0`.

| Rows | Dense baseline median ms | Candidate-max atomic median ms | Atomic speedup |
| ---: | ---: | ---: | ---: |
| 1 | 2.5982 | 2.6685 | 0.9737x |
| 2 | 2.6129 | 2.6639 | 0.9808x |
| 3 | 2.5659 | 2.6637 | 0.9633x |
| 4 | 2.5704 | 2.6735 | 0.9614x |

The non-atomic candidate-max path in the same run was also exact and landed in
the same range (`0.961x-0.980x`), so the extra reducer launch was not the
dominant problem. The full-vocab scan itself plus less mature scheduling than
oneDNN is enough to lose.

## Decision

Closed as **no-win**:

- do not integrate `int8_lm_head_candidate_max_atomic_w8a8` into vLLM;
- do not submit or promote this diagnostic-only result;
- do not keep this patch active in a production source tree unless deliberately
  reviving kernel research.

The Qwen27 `100+ tok/s` route should now focus on one of:

1. removing whole LM-head/logits calls in the verifier path while keeping exact
   target verification and bonus-token semantics;
2. improving accepted tokens per verifier step with a stronger fresh-request
   draft source;
3. a deeper producer-integrated path that fuses into the existing dense GEMM
   epilogue or otherwise avoids a separate full-vocab scan/reduction.

