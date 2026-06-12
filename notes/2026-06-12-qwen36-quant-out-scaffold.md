# Qwen3.6 35B INT8 Quant Out-Variant Scaffold

Date: 2026-06-12

## Why This Exists

The current route-exact MoE replay shows that the best exact staged path is
still too slow for the `>200 tok/s` single-request target, but it also shows a
lot of avoidable intermediate allocation and dispatch structure around the
small-M W8A8 MoE path. This scaffold adds quantization out-variants so future
fixed-shape layerlet and route-replay experiments can reuse preallocated
buffers instead of allocating fresh quant outputs and scales for every pass.

This is plumbing only. It is not promoted to the accepted endpoint and it does
not claim a new serving speed result.

## Source Changes

Kernel source tree:

- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/quantization/int8_quant.cpp`
  - Added strict out-variant APIs:
    - `per_token_quant_int8_xpu_out(x, q, scales)`.
    - `silu_and_mul_quant_int8_xpu_out(x, q, scales)`.
  - Out variants require contiguous XPU tensors, matching devices, int8 output
    tensors, float32 scale tensors, and exact output shapes.
  - The math path is the same as the existing allocating kernels.
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/ops.h`
  - Declared both out-variant functions.
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp`
  - Registered both schemas under `torch.ops._xpu_C`.
- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
  - Added fake registrations and helper wrappers.
  - Uses scratch-provided `gemm1_a`, `gemm1_a_scales`, `gemm2_a`,
    `gemm2_a_scales` when present, and falls back to the allocating path when
    absent.

vLLM source tree:

- `/home/steve/src/vllm/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`
  - Extends the existing opt-in `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE` scratch
    allocation with quant output and scale buffers.

Tracking repo:

- `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`
  - Added `_per_token_quant_int8_maybe_out`.
  - Adds quant scratch buffers to the route replay.
  - Records whether `per_token_quant_int8_xpu_out` is available in benchmark
    output and markdown.
  - Stays compatible with the currently installed package by falling back to
    the existing allocating op when the new op is absent.

## Validation Completed

Static Python compile:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py \
  /home/steve/src/vllm/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py \
  /home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py
```

Diff whitespace checks:

```bash
git -C /home/steve/src/vllm-xpu-kernels diff --check -- \
  csrc/xpu/quantization/int8_quant.cpp \
  csrc/xpu/ops.h \
  csrc/xpu/torch_bindings.cpp \
  vllm_xpu_kernels/fused_moe_interface.py

git -C /home/steve/src/vllm diff --check -- \
  vllm/model_executor/layers/fused_moe/experts/xpu_moe.py

git -C /home/steve/llm-optimizations diff --check -- \
  scripts/bench-qwen36-int8-moe-kernels.py
```

Native build gate:

```bash
cmake --build /home/steve/src/vllm-xpu-kernels/build/temp \
  --target _xpu_C -j 8
```

Built artifact import check:

```bash
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/build/temp:$LD_LIBRARY_PATH \
/home/steve/.venvs/vllm-xpu/bin/python - <<'PY'
import importlib.util
import torch

path = "/home/steve/src/vllm-xpu-kernels/build/temp/_xpu_C.abi3.so"
spec = importlib.util.spec_from_file_location("_xpu_C", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("per_token_out", hasattr(torch.ops._xpu_C, "per_token_quant_int8_xpu_out"))
print("silu_out", hasattr(torch.ops._xpu_C, "silu_and_mul_quant_int8_xpu_out"))
print(torch.ops._xpu_C.per_token_quant_int8_xpu_out)
PY
```

Observed output:

```text
per_token_out True
silu_out True
_xpu_C.per_token_quant_int8_xpu_out
```

No XPU route-replay correctness or timing benchmark was run in this pass
because the accepted backend was live and all four B70s were already near full
VRAM use by the production workers.

## Promotion Gate

The next clean benchmark window should:

1. Run the layer-9 routecapture6 rows=1 replay with the patched `_xpu_C`
   artifact available in an isolated lane.
2. Confirm `quant_out_op_available=True`.
3. Compare current `xpu_fused_moe`, scratch `xpu_fused_moe`, exact
   preallocated staged, and quant-out preallocated staged.
4. Require `max_abs_diff=0.0` against current `xpu_fused_moe`.
5. Reject the branch if speed is neutral or worse after warmup.
6. Keep the accepted endpoint untouched unless the replay and short quality
   gates both pass.

Expected effect by itself is small. The main value is feeding the persistent
MoE layerlet work by eliminating one class of hidden allocation and making the
scratch ABI explicit.

## What To Try Next

- Add the same strict out-variant discipline to gather/unpermute buffers if the
  layerlet still has allocation churn after quant-out.
- Build a single layer-9 persistent layerlet that consumes the scratch ABI
  directly. Pass/fail target remains roughly `<=168 us/layer`.
- Use VTune or Level Zero metrics to check whether the quant kernels are
  launch-bound, bandwidth-bound, or failing to hit XMX/DPAS paths.
- Keep fused SiLU+quant behind an exactness gate. The earlier fused path drifted
  and cannot be promoted until route replay reports exact parity.

## Route Replay Result

Run tag: `20260612am`

The accepted backend was stopped only after the public frontdoor reported zero
active and queued requests and remained paused for remote traffic. The replay
used a temporary package overlay:

```text
PYTHONPATH=/tmp/qwen36-quant-out-overlay:/home/steve/src/vllm
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/build/temp:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels
```

The overlay imported the patched build artifact and confirmed:

```text
per_token_out True
silu_out True
moe_prologue True
```

Benchmark command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1 \
  --iterations 30 \
  --warmup 10 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-start-indices '0:64:4' \
  --output-json data/qwen36-quark-int8-moe-routecapture6-layer9-quant-out-scaffold-20260612am.json \
  --markdown-out data/qwen36-quark-int8-moe-routecapture6-layer9-quant-out-scaffold-20260612am.md
```

Results over 16 layer-9 routecapture6 rows=1 windows:

- `quant_out_op_available`: true for all rows.
- Current `xpu_fused_moe`: `299.072 us/layer` mean.
- Scratch `xpu_fused_moe`: `248.626 us/layer` mean.
- Exact preallocated staged with quant-out buffers:
  `207.237 us/layer` mean, `189.067 us` min, `243.521 us` max.
- Fused-prologue staged: `282.710 us/layer` mean.
- Exactness:
  - Manual staged versus `xpu_fused_moe`: `max_abs_diff=0.0`.
  - Scratch `xpu_fused_moe`: `max_abs_diff=0.0`.
  - Preallocated staged: `max_abs_diff=0.0`.
  - Fused-prologue staged: `max_abs_diff=0.0`.

Decision:

- Keep the quant-out scaffold. It is exact and improves the exact preallocated
  staged path compared with the previous no-out replay (`216.361 us/layer`) and
  active-offset gate replay (`226.882 us/layer`).
- Do not promote it to the endpoint by itself. `207.237 us/layer` is still well
  above the `~168 us/layer` non-speculative budget for `>200 tok/s` c1 decode,
  and the accepted source-package binary was left untouched.
- Feed this scratch ABI into the persistent MoE layerlet work. The next
  meaningful speed target remains a one-dispatch layerlet or equivalent
  resident MoE worker.

Restore/provenance:

- Accepted backend relaunched in tmux session
  `qwen36-tp4-accepted-restored-after-quantout-20260612am`; `/health` returned
  after `64s`.
- Source-package import after restore confirmed:
  - `per_token_quant_int8_xpu_out`: absent.
  - `silu_and_mul_quant_int8_xpu_out`: absent.
- Accepted provenance guard passed both prompt cases and all sentinel tokens:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-quantout-20260612am.json`.
