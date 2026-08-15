# Reproduce the Qwen3.6 27B AutoRound INT4 TP2 record

The authoritative standalone packet is
[`../../repro/qwen36-27b-autoround-int4-b70/README.md`](../../repro/qwen36-27b-autoround-int4-b70/README.md).

It now includes the material that was missing from the earlier recipe:

- exact public source anchors;
- small Git bundles containing both local-only committed continuations;
- the exact dirty vLLM and XPU-kernel patches captured by the record run;
- model file sizes and hashes;
- Intel 2025.3/PyTorch 2.11/oneCCL runtime identity;
- a closed record environment;
- model download, source restore, build, run, and verification helpers;
- the original isolated and swapped-crossover run directories in a
  deterministic checksummed archive;
- strict, repeat128, baseline, needle, and LocalMaxxing evidence.

The record is **AutoRound INT4 W4A16 on vLLM/XPU with target-verified MTP3**.
It is not the separate Q8_0 GGUF llama.cpp/SYCL result.

Quick offline validation:

```bash
cd /path/to/llm-optimizations
python3 repro/qwen36-27b-autoround-int4-b70/scripts/verify-packet.py
```

Historical pre-transaction and TP1 recipes were retained in
[`reproduce-legacy.md`](reproduce-legacy.md); they are not the 95.385 tok/s
record recipe.
