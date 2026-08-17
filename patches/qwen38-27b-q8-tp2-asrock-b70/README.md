# Qwen3.8 27B Q8_0 TP2 lab patch

This packet restores the complete one-chain source snapshot used by the
quality-gated Qwen3.8 Q8 TP2 result, then applies the accepted Qwen3.8-only
recurrent-quad SG16 and SG24 increments. Qwen3.8 uses the same admitted Qwen3.5
architecture paths as the Qwen3.6 target, so the large canonical base artifact
is shared rather than duplicated.

## Correct identity

- base fork: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- base commit: `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- canonical artifact:
  [`llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64`](../qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64)
- decoded patch SHA-256:
  `c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7`
- scope: 19 files, 4,814 insertions, 102 deletions
- Q8 inner dot product: one DP4A chain (the later DP4A2 schedule is excluded)
- Qwen3.8 incremental patch:
  [`recurrent-quad-sg16-20260817.diff`](recurrent-quad-sg16-20260817.diff)
- incremental patch SHA-256:
  `05ce95e18a211deeb20348ad6a2ffd4ca2dee828d7692c4a026f055156e9c86c`
- incremental runtime door: `GGML_SYCL_MMVQ_Q8_QUAD_SG16=1`
- SG24 incremental patch:
  [`recurrent-quad-sg24-20260817.diff`](recurrent-quad-sg24-20260817.diff)
- SG24 patch SHA-256:
  `863ad19b3df13c9edd1d0d9b595c04a2baa92e67efc6df82cd9beb2beea54db4`
- promoted runtime door: `GGML_SYCL_MMVQ_Q8_QUAD_SG24=1` (takes priority;
  set it to zero to recover the SG16 control)

The complete snapshot includes the three runtime doors used in the captured
Qwen3.8 result: vec4 TP root reduction, fused Q/K RMS+scale+RoPE, and fused
recurrent conv+SiLU+Q/K-L2. The earlier local artifact named
`llama-cpp-mndodd-4302fb599-qwen38-q8-tp2-20260816.diff.gz.b64` omits those
three increments and is retained only to explain old hashes. It is
**superseded and must not be used to reproduce the headline result**.

## Restore

```bash
git clone https://github.com/mndodd/llama.cpp.git llama.cpp-qwen38-q8-tp2
cd llama.cpp-qwen38-q8-tp2
git checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

base64 -d \
  /path/to/b70-optimization-lab/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64 \
  | gzip -dc > /tmp/qwen38-q8-tp2.patch
sha256sum /tmp/qwen38-q8-tp2.patch
git apply --check /tmp/qwen38-q8-tp2.patch
git apply /tmp/qwen38-q8-tp2.patch

sha256sum \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff
git apply --check \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff
git apply \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff

sha256sum \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff
git apply --check \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff
git apply \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff
git diff --check
```

All three hashes must match the values above. The increments change only the fused
recurrent GDN-quad workgroup population for the exact equal-TP2 local shape
`K5120/N5120+3072+24+24`, first from 8 to 16 and then from 16 to 24 SG16 rows
per workgroup; each output row retains the same SG16 DP4A body and
FP32 reduction order. Build and runtime settings are in
the [standalone reproduction](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md).
The provenance correction and fresh exact replay are recorded in the
[audit note](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-repro-provenance-correction.md).
