# Qwen3.6/3.8 llama.cpp SYCL graph-evidence port

This packet contains a minimal source patch for the clean accepted Qwen TP1
overlay at llama.cpp commit
`fa0f3b25a47f346858a4d0d169f5181aa424b110`.

The patch is intentionally limited to two files:

- `ggml/src/ggml-sycl/common.hpp` adds bounded executable-graph cache state and
  report counters to each SYCL backend context;
- `ggml/src/ggml-sycl/ggml-sycl.cpp` adds the cache-size control, complete
  graph signatures, power-of-two progress markers, the shutdown summary,
  direct replay, and the capture-safe `CONCAT` compatibility distinction.

It does not include the historical cycle timer, DFlash/MTP executor changes,
new fusions, kernel changes, server changes, or changes to the accepted Qwen
optimization overlay. Graphs and the persistent cache remain default-off.

## Identity

- patch: [`llamacpp-fa0-graph-cache-evidence-port-20260825.patch`](llamacpp-fa0-graph-cache-evidence-port-20260825.patch);
- patch SHA-256:
  `1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892`;
- exact pre/post file identities:
  [`source-manifest.json`](source-manifest.json);
- exact base: `fa0f3b25a47f346858a4d0d169f5181aa424b110`;
- base `common.hpp` SHA-256:
  `25e2323e6199c25b840c4c2f5729389963358faa892de1ee6b71a08619ac7be8`;
- base `ggml-sycl.cpp` SHA-256:
  `561a275ca5abfc437fdbf126a5d1b475755558d6cec9cac3f5f66d1af8c241bd`;
- changed paths: two;
- diff size: `215` insertions, `21` deletions.

The implementation was extracted from the tracked July persistent-cache
packet and the sealed 2026-08-25 R5 sentinel behavior, then rebased manually
onto `fa0f3b25`. The historical phase-one patch does not apply cleanly to this
base and contains many unrelated changes, so it must not be applied wholesale.

## Preserved behavior

The base's per-device graph policy is retained. In particular, this patch does
not restore the obsolete global `device_count > 1` rejection. Each SYCL
backend still records only its own device-local scheduler subgraph.

The `CONCAT` relaxation matches the actual base implementation:

- contiguous dimension-3 concat performs blocking `memcpy(...).wait()` and
  remains rejected;
- dimension 0/1/2 and non-contiguous concat use submitted kernels without a
  blocking wait and are allowed into capture.

With `GGML_SYCL_GRAPH_CACHE_SIZE=0`, the existing record/update/recreate path
remains active. A positive value enables a bounded immutable executable cache;
the value is clamped to `0..64`. A full cache falls back to eager execution
instead of evicting an executable that may still be in flight.

## Static validation

Run the durable contract check before applying the patch:

```bash
python3 experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_fa0_graph_cache_port_patch.py \
  --source /path/to/clean/llama.cpp-at-fa0f3b25
```

The check verifies the patch hash, exact two-file scope, required evidence
markers, preserved per-device policy, base file hashes, and
`git apply --check` against a clean exact-base source. It never applies the
patch.

Application and build are separate authorized steps. Do not patch the proven
graph-off build directory or compare a rebuilt graph-on binary's output oracle
directly with the old binary; the preregistration requires same-new-binary
graph-off versus graph-on parity.

## Evidence boundary

This is an unbuilt, unrun candidate patch. It grants no graph, speed, depth,
quality, TP2, TP4, or publication authority. The frozen mechanism and
interpretation gates are in the linked
[preregistration](../../experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-fa0-graph-cache-port-preregistration.md).
