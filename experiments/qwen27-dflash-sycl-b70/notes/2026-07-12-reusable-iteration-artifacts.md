# 2026-07-12 Reusable Iteration Artifacts

## Result

Implemented checksum-admitted diagnostic artifacts for the Qwen27/B70 kernel
loop. This improves iteration and reproducibility only; it is not a decode
optimization and none of these warm/reused artifacts are promotion evidence.

`scripts/qwen27-iteration-artifacts.py` now provides:

- a build/module fingerprint over the llama.cpp commit and dirty patch, CMake
  cache, relevant binaries, kernel, and Intel userspace;
- deterministic Q4_0 weights, Q8_1 activations, and FP32 reference outputs for
  `M=1/4/8/16`, `K=5120`, and `N=256`;
- recursive pack registration and checksum re-admission keyed by source model,
  packer revision, layout, and payload identity;
- a focused backend runner with exact-build successful-result reuse only when
  explicitly requested.

## Validation

- Python bytecode compilation passed.
- Golden preparation completed in `3.04 s`; all nine tensor files passed deep
  SHA-256 verification.
- The focused SYCL suite passed Q4_0 reorder widths 1-17 plus the SwiGLU/Q8 and
  residual/RMS/Q8 boundaries on GPU0.
- Re-running with `--reuse-pass` found the exact build/run key and returned the
  admitted result without launching the tests again.
- A diagnostic Q4_0 payload was registered and deep-verified through the pack
  registry, proving the admission/reuse flow without creating another model
  copy.

Artifacts live outside Git under
`/mnt/fast-ai/bench-results/qwen27-tp1-worker-harness/iteration-v1/`.

## Honest Remaining Boundary

The current SYCL reorder happens into GPU-only allocations during model load.
There is no loader ABI that binds a serialized reordered full-model pack, so
the registry can safely admit externally emitted packs but cannot make the
runtime consume one. The generated golden tensors are representative synthetic
kernel contracts, not captured Qwen activations or pristine KV/GDN states.
Those require inference-source hooks and remain unimplemented.
