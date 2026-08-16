# Qwen3.8 27B Q8_0 TP2 lab patch

This directory freezes the exact source delta used for the quality-gated
Qwen3.8 27B Q8_0 two-B70 result captured on 2026-08-15 and rechecked on
2026-08-16.

## Identity

- base fork: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- base commit: `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- patch artifact:
  `llama-cpp-mndodd-4302fb599-qwen38-q8-tp2-20260816.diff.gz.b64`
- decoded patch SHA-256:
  `642032df8459e05bbaea00c3ff5f7e93d657c995979164a85eb9262747fa6b1e`
- scope: 18 files, 3,715 insertions, 100 deletions

The snapshot is intentionally separate from the later Qwen3.6 DP4A2 patch.
It identifies the binary and source actually used for the accepted Qwen3.8
Q8 result; do not silently substitute another historical source increment.

## Restore

```bash
git clone https://github.com/mndodd/llama.cpp.git llama.cpp-qwen38-q8-tp2
cd llama.cpp-qwen38-q8-tp2
git checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

base64 -d \
  /path/to/b70-optimization-lab/patches/qwen38-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-qwen38-q8-tp2-20260816.diff.gz.b64 \
  | gzip -dc > /tmp/qwen38-q8-tp2.patch
sha256sum /tmp/qwen38-q8-tp2.patch
git apply --check /tmp/qwen38-q8-tp2.patch
git apply /tmp/qwen38-q8-tp2.patch
git diff --check
```

The decoded hash must match the value above. Build and runtime settings are in
the [standalone reproduction](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md).
