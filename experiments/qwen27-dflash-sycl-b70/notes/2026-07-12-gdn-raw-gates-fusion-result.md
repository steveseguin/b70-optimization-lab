# GDN raw-gate fusion result

`GGML_SYCL_FUSE_GDN_RAW_GATES=1` moves the scalar recurrent gate pipeline into
the SYCL GDN kernel.  For each matched recurrent layer it consumes raw alpha,
raw beta, `dt`, and `a`, computes sigmoid/softplus/scaling in the GDN launch,
and skips the four separate SIGMOID, ADD, SOFTPLUS, and MUL graph nodes.  The
matcher requires single-use contiguous device-local F32 tensors and composes
with `GGML_SYCL_FUSE_GDN_CACHE`.

Validation established that the actual Qwen graph matches (power-of-two
counters reached hundreds during a short decode), the consolidated JIT and AOT
builds pass, focused M=1/M=4 fused-quant regression tests pass 8/8, and the
fixed temperature-zero 128-token Rayleigh-scattering response remains
semantically correct.

The optimization is rejected for the production MTP3 stack.  An AOT eight-run
four-card crossover, with assignments reversed between rounds, measured:

- raw gates on: `47.4455`, `46.6113`, `46.1327`, `45.0941` tok/s, mean
  `46.3209`;
- raw gates off: `49.8065`, `50.3551`, `50.6160`, `47.7518` tok/s, mean
  `49.6323`;
- delta: `-6.67%`.

Every strict run passed and every run reported zero cached prompt tokens.  The
likely cause is that transcendental gate work and its live values increase
pressure inside the already substantial GDN kernel; removing four tiny
launches does not compensate.  Keep the flag default off.  Do not repeat this
fusion boundary without a measured kernel-level occupancy/register redesign.

Artifacts are the `mtp3-rawgates-cross1-*` and
`mtp3-rawgates-cross2-*` JSON files under
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.
