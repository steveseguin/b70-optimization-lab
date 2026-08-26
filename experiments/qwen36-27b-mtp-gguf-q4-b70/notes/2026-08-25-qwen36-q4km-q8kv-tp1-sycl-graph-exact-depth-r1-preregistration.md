# Qwen3.6 embedded-MTP Q4_K_M/q8_0-KV TP1 SYCL-graph exact-depth R1

State: **sealed and preregistered; not launched**.

This create-only packet overlays the committed Q4_K_M/F16 graph packet. The sole execution delta is `-ctk q8_0 -ctv q8_0` plus the matching `kv=q8_0` selector and distinct campaign lifecycle. The checksum-pinned Q4_K_M model/artifact, TP1 MTP0 target-only execution, source and three-patch chain, graph backend, binary and 32-DSO closure, cache-8 environment, verbose JSON output, phase-aware graph gates, and exact 0/2K/4K/8K/16K/24K/32K contexts remain identical.

The packet binds the accepted graph-off `q36-q4km-tp1-kv-q8-context` result as its matched comparison identity. No graph-off speed or authority transfers. There is no speed floor, and a slower result is still evidence. Every cell requires its own prefill and decode graph evidence; no estimates are allowed.

This packet grants no quality, site, record, submission, or protected-value replacement authority. A separate quality battery is required before publication.

Static check:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-r1.py --check
```

Exact launch acknowledgement after a clean committed-main and idle-GPU preflight:

```text
RUN qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-20260825-r1
```
