# 2026-07-12 SSM convolution + SiLU fusion result

The guarded `GGML_SYCL_FUSE_SSM_CONV_SILU` experiment writes the SiLU result
directly from the depthwise SSM convolution kernel, removing one launch and
the raw-convolution intermediate for every GDN layer. An explicit volatile
F32 boundary preserves the standalone convolution's rounding behavior.

Correctness passed a deterministic 128-token generation with content exactly
matching the control Rayleigh-scattering answer. A JIT `llama-bench` pair was
`26.5360` on versus `26.3980 tok/s` off (+0.52%).

The full AOT four-card MTP3 crossover was neutral. Across both card
assignments the on average was `48.653 tok/s`; off was `48.677 tok/s`
(-0.05%). All eight strict runs passed and all reported prompt-cache counts
zero. The first assignment appeared positive, but reversing the flags removed
the apparent win.

This is not promoted. The implementation remains default-off as a useful
building block for a larger GDN pipeline kernel. Isolated one-launch fusion is
below the noise floor; future GDN work must collapse multiple state, conv,
normalization, gate, and commit operations together.

Artifacts are the `mtp3-ssm-silu-*` JSON files under
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.
