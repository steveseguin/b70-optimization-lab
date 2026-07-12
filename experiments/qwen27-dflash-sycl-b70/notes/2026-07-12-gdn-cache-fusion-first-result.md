# 2026-07-12 GDN snapshot-cache fusion first result

The guarded `GGML_SYCL_FUSE_GDN_CACHE=1` lane ports llama.cpp CUDA's mature
GDN cache-fusion design to SYCL. The graph matcher recognizes
`GATED_DELTA_NET -> snapshot-tail VIEW -> CPY(cache)` with exact F32 shapes,
strides, device buffers, and rollback-slot count. The GDN kernel then writes
each state snapshot directly to the persistent cache and the graph loop skips
the tail CPY and intervening views.

For Qwen27, each recurrent state is `128*128*48 = 786432` F32 values (3 MiB)
across 48 recurrent layers. The fusion removes 48 CPY submissions and about
288 MiB of tail-write plus tail-read traffic per M=1 pass. At MTP3 verifier
width it can avoid roughly 1.125 GiB per cycle.

## Validation

- JIT no-spec deterministic 128-token content exactly matched the control.
- Three-repetition JIT no-spec was `26.9102` versus `26.4446 tok/s` (+1.76%)
  on top of the repaired RMS/Q8 and SwiGLU/Q8 fusion lane.
- Eight AOT strict MTP3 crossover runs used both flag assignments on all four
  B70s. Every run passed and every prompt-cache count was zero.
- Across both assignments the fused average median was `50.390 tok/s`; the
  control average was `48.796 tok/s`, a repeatable +3.27%.
- A separate deterministic strict pair measured `50.5719` versus `48.0915
  tok/s`; response hashes were not all equal, but the same harness is not
  bit-deterministic across separate MTP runs, so this is not treated as a byte
  parity proof.
- Q4_0 reordered MMVQ widths 1 through 17 still pass after the consolidated
  AOT build.

This is the first fusion whose benefit grows materially at speculative width.
It remains default-off until rollback-slot byte comparisons are added, but it
is the current promotion candidate. The next high-value work is stateless GDN
pipeline fusion: convolution preparation/SiLU/QK normalization, alpha/beta
post-processing inside GDN, and the output norm/gate epilogue.

Artifacts are `mtp3-gdn-swiglu-*` and `mtp3-deterministic-gdn-*` under
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.
