# Qwen3.8 27B Q8_0 TP2 lab patch

This packet points to the complete one-chain source snapshot used by the
quality-gated Qwen3.8 Q8 TP2 result. Qwen3.8 uses the same admitted Qwen3.5
architecture paths as the Qwen3.6 target, so the canonical artifact is shared
rather than duplicated.

## Correct identity

- base fork: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- base commit: `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- canonical artifact:
  [`llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64`](../qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64)
- decoded patch SHA-256:
  `c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7`
- scope: 19 files, 4,814 insertions, 102 deletions
- Q8 inner dot product: one DP4A chain (the later DP4A2 schedule is excluded)

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
git diff --check
```

The decoded hash must match the value above. Build and runtime settings are in
the [standalone reproduction](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md).
The provenance correction and fresh exact replay are recorded in the
[audit note](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-repro-provenance-correction.md).
