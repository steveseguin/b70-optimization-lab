# Qwen3.6 Q4_0 TP1 exact-depth r1 failure

Date: 2026-08-25. State: **failed closed; no matrix cells published**.

The one preregistered `llama-bench` process completed all 14 raw rows for the
seven requested depths. The host remained responsive, GPU0 stayed compute
active during the run, the kernel journal recorded no GPU reset/hang/fault,
OOM, or segmentation marker, and postflight found no model process,
container, or render-node owner.

The campaign nevertheless failed its frozen post-benchmark gate. This build
9976 binary wrote an empty stderr log, so it could not attest the required
`GGML_SYCL_ENABLE_GRAPH: 0` and `GGML_SYCL_GRAPH_CACHE_SIZE: 0` strings. The
controlled environment requested both values, but the preregistration required
runtime log evidence as well; that requirement cannot be waived after seeing
the output.

The complete create-only root is
`/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r1`.
The tracked failure record preserves its hashes and the seven unpromoted raw
pairs at
`experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1-failure.json`.

No retry was made. A future r2 must preregister a graph-off attestation that
this exact historical binary can actually supply—for example a bounded static
or source/binary capability proof—before launch. It must not simply delete the
failed gate or promote these raw rows after the fact.

There is also a cross-session coordination caveat. Another writer committed a
Qwen3.8 `llama-batched-bench` GPU0 result at 10:26 local, inside this
campaign's 10:22–10:38 wall interval. This runner's process scan did not match
`llama-batched-bench`. Its preflight found GPU0 idle, but a process starting
after preflight cannot be excluded. Before any GPU r2, the canonical exclusion
gate must cover `llama-batched-bench` and every active session must take the
same host/GPU lock.
