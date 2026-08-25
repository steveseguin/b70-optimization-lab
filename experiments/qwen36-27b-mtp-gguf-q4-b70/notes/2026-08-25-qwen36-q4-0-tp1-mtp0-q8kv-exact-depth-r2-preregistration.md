# Qwen3.6 Q4_0 TP1 exact-depth r2 attested-rerun preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

R1 remains failed and quarantined. Its `10:22:09`–`10:38:40` local run
overlapped the Qwen3.8 GPU0 `llama-batched-bench` result committed at
`10:26:34` in `c5f880c94`. Therefore none of r1's 14 raw rows may be reused or
published, even though the separate r2 static proof can establish graph-off.

R2 is a fresh rerun with the same exact Qwen3.6 Q4_0 artifact, build-9976
`llama-bench`, q8_0 K/V, FlashAttention-on, MTP0, and seven depths. It uses the
new create-only root
`/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r2`.

Before the GPU subprocess starts, the runner fail-closed verifies:

- the frozen model, executable, implementation, parser, library chain, and r1
  failure artifacts;
- the exact `libggml-sycl.so` SHA-256;
- build receipts showing graph support compiled with `GGML_SYCL_GRAPH`;
- committed source showing the default-zero environment load and graph-entry
  guard; and
- exact DSO disassembly showing `GGML_SYCL_ENABLE_GRAPH` loaded with default
  zero and zero branching directly to ordinary graph compute.

The controlled subprocess environment sets `GGML_SYCL_ENABLE_GRAPH=0` and
`GGML_SYCL_GRAPH_CACHE_SIZE=0`. Runtime stderr marker strings are not required:
this exact `llama-bench -o json` path produced an empty stderr in r1. The static
attestation is written before launch as `graph-off-attestation.json`.

R2 acquires the Muse lock, host benchmark lock, `/tmp/b70-gpu0.lock`, and the
canonical GPU0 lease before any process scan or run-root creation. It explicitly
scans for `llama-batched-bench` and repeats the idle/render-owner scan under all
four locks immediately before launch.

After this packet is committed and pushed cleanly, the exact command is:

```bash
env -u LD_LIBRARY_PATH -u LIBRARY_PATH \
  python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r2.py \
  --execute \
  --ack 'RUN qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r2 d1-exact-depths r2'
```

Any identity, attestation, lock, idle, benchmark, parser, row-shape, or receipt
failure leaves all seven cells unfilled. Passing r2 adds raw-engine measurements
only; quality remains separately labeled and no historical result is lowered.
