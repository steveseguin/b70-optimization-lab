# Laguna M8 actual-model driver-config serialization abort

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v6 actual-model gate completed arm A's offline generation and
raw-evidence aggregation, then failed closed while serializing `driver.json`.
Arms B and C did not start. This is a driver-evidence bug, not a
model-correctness, graph-parity, performance, benchmark, payload, or
LocalMaxxing result.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b0174430b-20260724T174418Z
```

It must never be reused. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## What completed

The target and DFlash loaded from internal NVMe. The corrected exact
target-plus-draft slot contract passed on all four ranks. `LLM.generate`
returned exactly one output object, the driver accepted
`num_cached_tokens == 0`, and the raw aggregator completed.

The retained `evidence/evidence.json` contains exactly 15 eligible M=8 events
on each of four ranks under raw-evidence V2 / aggregate gate V7. Every
completed low-level manifest has 201 events and the aggregate includes the
48-layer live slot-routing vectors. This proves that the preceding 54-key
observer correction passed its actual-model path.

The returned completion token list was held only in process memory and was not
persisted before the later exception. Recorder post-bookkeeping emitted IDs
are internal verifier evidence and must not be relabeled as the API-returned
completion.

## Exact failure and root cause

After aggregation, the driver's final `json.dumps(record)` raised:

```text
TypeError: Object of type ModelConfig is not JSON serializable
```

vLLM's `EngineArgs.create_speculative_config` updates the caller-provided
speculative-config dictionary in place with `target_model_config` and
`target_parallel_config`. The driver retained that same dictionary for its
final evidence record. By the time serialization ran, it contained a live
`ModelConfig` object.

The safe correction is to take canonical JSON-deep snapshots of engine,
speculative, and compilation configurations before constructing `LLM`, pass a
detached decode to vLLM, and decode the immutable pre-LLM JSON again for the
driver record. This is driver-evidence isolation; it does not touch model
execution.

There is no `driver.json` or final A/B/C `analysis.json`. B/C never started.
Cleanup completed, pre/post worker reports are empty, post-idle passed on all
four devices, and no model worker remains.

## Frozen identities and artifacts

- main tooling:
  `b0174430bc10add179f210c6990516995d852265`;
- preregistration:
  `ca9429a99`;
- vLLM:
  `e25867aa698f82cbf2fb835e26807078674acebc`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- RPC path:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p6-a`;
- sealed root and arm mode: `0500`.

Key retained hashes:

```text
74a4fd85b2b9349a5b2edfc69d2e6c4f4a18a84baa4ac5fe6594f31051ef16c1  identity.txt
67743dc1f29b6ef52f5a4a71cb487234bd5c3c0fd54ee1e7c1c4dc478af67192  incumbent-eager/stdout.log
25094c0e7c79a9cbfedeba467bcded55db6fad1836d05b05d5f7c72661aeaffb  incumbent-eager/stderr.log
32f7f2e461572dd4037c1ad55470f26d8f3c4a9683197d7df81b30d37fd13cc5  incumbent-eager/evidence/evidence.json
fec123f6b5580fef2b89cf1a9c6a685fd73df18f57a321577cf2a884f2d2dd4d  incumbent-eager/pre-idle.json
d9f69f9e284fb5af3ff4747a66754e6a33ed5867a974938e50f98c5a0d6528eb  incumbent-eager/post-idle.json
```

Machine-readable classification:
`data/laguna-m8-actual-offline-driver-config-serialization-abort-20260724.json`.
