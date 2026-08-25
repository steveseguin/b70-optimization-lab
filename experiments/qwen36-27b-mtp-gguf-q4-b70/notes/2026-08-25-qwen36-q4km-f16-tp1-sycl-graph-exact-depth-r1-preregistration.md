# Qwen3.6 embedded-MTP Q4_K_M/F16 TP1 SYCL-graph exact-depth R1

State: **sealed and preregistered; not launched**.

This create-only packet mechanically overlays the passed embedded-MTP Q8_0/F16 graph packet. Its only execution-identity change is the complete model/artifact identity: Q4_K_M from `unsloth/Qwen3.6-27B-MTP-GGUF` at revision `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, 17,106,773,120 bytes, SHA-256 `a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`. The artifact contains MTP tensors, but this remains target-only MTP0 with no draft tokens.

The packet preserves TP1, F16 K/V, graph-on cache 8, FlashAttention, verbose JSON output, the three-patch source chain, binary/backend/32-DSO closure, environment, five-repetition `pp2048`/`tg128` workload, phase-aware graph gates, and exact active contexts 0/2K/4K/8K/16K/24K/32K. It binds the accepted graph-off `q36-q4km-tp1-kv-f16-context` result only as the matched comparison identity; none of its speed or authority transfers.

There is no speed floor. Every cell must retain separate prefill and decode graph evidence. The packet grants no estimate, quality, site, record, submission, or protected-value replacement authority. A separate quality battery is required before publication.

Static check:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-sycl-graph-exact-depth-r1.py --check
```

The exact launch acknowledgement, only after a clean committed main and idle-GPU preflight, is:

```text
RUN qwen36-q4km-f16-tp1-sycl-graph-exact-depth-20260825-r1
```
