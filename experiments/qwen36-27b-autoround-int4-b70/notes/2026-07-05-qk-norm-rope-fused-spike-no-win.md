# Qwen27 QK-Norm + RoPE Fusion Spike: No Win

Date: 2026-07-05

## Summary

A read-only audit found that Qwen3Next full-attention layers spend measurable
forward time in separate Q/K Gemma RMSNorm plus M-RoPE calls. The existing XPU
`fused_qk_norm_rope` op cannot be used directly because Qwen3Next projects a
gated layout `[q, gate, k, v]`, while the generic op assumes `[q, k, v]`.

I implemented a default-off Qwen3Next-specific XPU prototype:

- new op: `torch.ops._C.fused_qwen3next_qk_norm_rope`;
- layout: in-place Q at offset `0`, K at offset `2*q_size`, gate/V untouched;
- semantics: Gemma RMSNorm, i.e. multiply by `1 + weight`, then text-only RoPE;
- vLLM hook: `VLLM_XPU_QWEN3NEXT_FUSED_QK_ROPE=1`, default off.

Patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-qk-norm-rope-fused-spike-20260705.patch`

## Build / Runtime Lesson

Do **not** build this XPU extension with oneAPI `2026.0` against the current
Torch `2.11.0+xpu` venv. That produced a binary requiring `libsycl.so.9` while
Torch supplies `libsycl.so.8`, and caused import/runtime instability.

Working narrow build loop for this spike used oneAPI `2025.3` and only the `_C`
target:

```bash
cd /home/steve/src/vllm-xpu-kernels
export CMPLR_ROOT=/opt/intel/oneapi/compiler/2025.3
export SYCL_HOME=/opt/intel/oneapi/compiler/2025.3
export PATH="$SYCL_HOME/bin:$PATH"
cmake -S . -B build/qkrope-2025 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DVLLM_TARGET_DEVICE=xpu \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain.cmake \
  -DVLLM_PYTHON_EXECUTABLE=/home/steve/.venvs/vllm-xpu/bin/python \
  -DVLLM_PYTHON_PATH="$(/home/steve/.venvs/vllm-xpu/bin/python - <<'PY'
import sys
print(':'.join(sys.path))
PY
)" \
  -DFETCHCONTENT_BASE_DIR=/home/steve/src/vllm-xpu-kernels/.deps \
  -DCMAKE_JOB_POOL_COMPILE:STRING=compile \
  -DCMAKE_JOB_POOLS:STRING=compile=8
cmake --build build/qkrope-2025 --target _C -j 8
cp build/qkrope-2025/_C.abi3.so vllm_xpu_kernels/_C.abi3.so
```

This avoids the full generated-attention rebuild and keeps the binary on the
Torch-compatible SYCL major.

## Kernel Parity

A direct Python parity sweep passed on Qwen27-shaped BF16 synthetic inputs:

- tokens: `1`, `4`, `32`;
- heads: `24` Q, `4` KV;
- `head_dim=256`, `rotary_dim=64`;
- launch policy: default and explicit one-head-per-subgroup;
- gate/V slices remained unchanged;
- Q/K matched PyTorch reference within BF16 tolerance.

`pytest` is not installed in the current venv, so the parity logic was run as a
direct Python probe.

## Strict Endpoint Result

Candidate:

- label: `qwen27-webhie-bf16scale-qkrope-fused-20260705T190145Z`;
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-qkrope-fused-20260705T190145Z-candidate-summary-20260705T190145Z.json`;
- bench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-qkrope-fused-20260705T190145Z-realistic128-chat-tokenids-qwensuite-20260705T190145Z.json`;
- raw run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-webhie-bf16scale-qkrope-fused-20260705T190145Z-20260705T190145Z`.

Result:

- strict fresh gate passed;
- `cached_tokens=0` on every prompt;
- median tokens 1-100 after TTFT: **45.980431175874045 tok/s**;
- p10: `43.106972319443535`;
- mean: `46.98498561281253`.

This is a large regression versus the current valid record
`65.27648650325429 tok/s`, so no quality run was needed and no LocalMaxxing
submission was made.

## Conclusion

Close this QK-norm+RoPE direct-fusion lane as a no-win for now. The likely
problem is that the simple one-head-per-subgroup custom op removes Python/kernel
launches but is slower inside the captured endpoint path than the current
separate primitives. A more aggressive multi-head/local-memory version was
unstable during early testing and should not be promoted without a separate
kernel microbench and parity gate.

Do not repeat this as another endpoint run unless a new kernel design first
beats the existing separate QK norm + rotary path in a standalone microbench.
The >100 tok/s path still requires stronger verified speculation, legal branch
regeneration, or a much larger target-forward reduction than this shallow fusion.
