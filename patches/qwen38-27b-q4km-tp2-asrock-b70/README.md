# Qwen3.8 27B Q4_K_M TP2 dense-FFN fusion

This directory preserves the incremental source delta for the 2026-08-15
target-only Qwen3.8 27B Q4_K_M result on two ASRock Intel Arc Pro B70 cards.
It adapts upstream llama.cpp's Q4_K gate/up/SwiGLU fusion to the lab's
per-device TP2 graph slices.

## Source identity

- Public base fork:
  <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- Clean public base commit:
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- Required full lab stack:
  [`../qwen36-27b-q8-tp2-asrock-b70/`](../qwen36-27b-q8-tp2-asrock-b70/README.md)
- Required full-stack decoded patch SHA-256:
  `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`
- This incremental artifact:
  `llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64`
- Incremental decoded patch SHA-256:
  `0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`
- Incremental scope: 3 files, 194 insertions, 1 deletion.
- Upstream inspiration: llama.cpp commit
  [`650913862`](https://github.com/ggml-org/llama.cpp/commit/65091386227039bfb81ee3426537656e3b4a3f83),
  [PR #26779](https://github.com/ggml-org/llama.cpp/pull/26779).

The upstream implementation correctly declines split-weight graphs because it
writes the unsliced output directly. The lab meta backend instead presents a
local graph to each SYCL device. This increment admits only those local,
contiguous, one-token Q4_K gate/up rows and writes that device's local SwiGLU
output. Every other graph falls back to the prior path.

## Restore and apply

First restore the full accepted TP2 stack exactly as documented in the linked
Qwen3.6 patch packet. Then apply this increment:

```bash
base64 -d \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64 \
  | gzip -dc > /tmp/qwen38-q4k-glu-tp2.patch

sha256sum /tmp/qwen38-q4k-glu-tp2.patch
git apply --check /tmp/qwen38-q4k-glu-tp2.patch
git apply /tmp/qwen38-q4k-glu-tp2.patch
git diff --check
```

The decoded hash must match the value above. Do not apply the incremental
artifact directly to the clean public fork; its context is the complete lab
TP2 stack.

## Build and runtime identity

Use the Release/BMG-G31 AOT build recipe in the full-stack packet with Intel
oneAPI DPC++/C++ `2026.1.1.20260724`. On the reference host the resulting
binaries were:

- `llama-server` SHA-256:
  `6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d`
- `llama-bench` SHA-256:
  `95a13668005d2dff3bdc6ea2eb48f339d8f6552b824a572207127db040a5926a`
- `libggml-sycl.so` SHA-256:
  `375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed`

Enable both required doors:

```bash
export GGML_SYCL_MMQ_Q4K_REORDER=1
export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1
```

Both default to off in source. `GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K_POISON=1`
is a deliberately invalid reachability control and must never be used for a
real result or service.

## Validation

- same-binary `llama-bench`, correct TP2 syntax (`SYCL0/SYCL1`, `1/1`),
  p64/n256/r5: `49.460273` off versus `50.271708 tok/s` on (`+1.6406%`);
- fused mechanism hits in that candidate row: `163,968`;
- fixed 12-prompt cold endpoint suite: `49.717503 tok/s` conventional median,
  up `1.7010%` from `48.885968`;
- 12/12 complete output SHA-256 hashes exactly matched the prior target-only
  oracle, all cached-token counts were zero, and `VERIFY_MISMATCH=0`;
- full-suite fused mechanism hits across both devices: `754,176`.

The source patch and runtime doors are necessary but not sufficient evidence.
Run the standalone repro and require its cache-zero and exact-hash gates.
