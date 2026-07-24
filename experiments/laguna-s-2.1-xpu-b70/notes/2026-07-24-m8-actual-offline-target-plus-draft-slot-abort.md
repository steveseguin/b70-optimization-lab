# Laguna M8 actual-model target-plus-draft slot-schema abort

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v5 actual-model raw-parity gate failed closed in arm A before
`LLM.generate` returned and before any evidence event. Arms B and C did not
start. This is a tooling-schema abort, not a model-correctness, graph-parity,
performance, benchmark, payload, or LocalMaxxing result.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-598dc430d-20260724T172414Z
```

It must never be reused. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Exact failure

The target and DFlash checkpoints loaded from internal NVMe, all four workers
initialized, and the first M=8 target verification reached the evidence hook.
Every worker then raised:

```text
RuntimeError: Laguna M8 evidence requires exactly 48 target attention slot mappings
```

The driver consequently received `EngineDeadError`; its `LLM.generate` call
did not return. The four recorder manifests are valid V2 manifests but each
contains `event_count=0` and no events. There is no `driver.json`,
`evidence.json`, or `analysis.json`.

The gate cleanup completed. All four workers logged shutdown, pre/post worker
reports are empty, post-idle accepted exactly the four `xpu-smi` observer rows,
and no model worker remains. The Python resource tracker reported one shared
memory object during abnormal shutdown; this does not change the sealed
classification.

## Root cause

The V2 helper incorrectly treated the global `slot_mappings` dictionary as a
target-only dictionary. `_get_slot_mappings` actually expands every layer in
every KV-cache group. With DFlash loaded, that static context contains both
target and draft attention layers.

The pinned source and model configs establish the exact topology:

- target: 48 keys,
  `model.layers.0..47.self_attn.attn`;
- DFlash draft: 6 keys,
  `model.layers.48..53.self_attn.attn`;
- full runtime mapping: exactly 54 keys.

The helper demanded that the full dictionary equal only the first 48 names, so
it deterministically rejected the six legitimate draft mappings before
writing the logical event key. This is observation-only tooling; it does not
implicate target arithmetic, DFlash acceptance, KV contents, XCCL, or graph
capture.

The next correction must require the exact 54-name target-plus-draft topology,
validate all mapping geometry fail-closed, and project only ordered target
layers 0-47 into the logical evidence vector. Unknown, missing, renamed, or
malformed target or draft mappings must fail. Draft mappings must never appear
in the 48-entry target vector.

## Frozen identities and artifacts

- main tooling:
  `598dc430deb8d090a75c9b294a6c584125521013`;
- preregistration:
  `aa00e4958`;
- vLLM:
  `00ba70bdbf4b5f9bd5714c288b98c54c91637c53`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- RPC path:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p5-a`;
- root and arm permissions after sealing: mode `0500`.

Key retained hashes:

```text
56c8f64048ffeeee0bd0bd5bdfd30bf603ba2917b408143f1e1b72e011e9facd  identity.txt
37d231a7c3cb83af9d1959bd0f62e4cdd15dcc5fd0fd26f8aca0a68e66c31da7  incumbent-eager/stdout.log
42d2f0d6122ab3bc73f40ec194ae16ccd938e8488fee3d55999311dac8d77af0  incumbent-eager/stderr.log
08d706bf9679b7db3438dec243a79c67555dbee56c763b0ed7659fcba6d0afc8  incumbent-eager/pre-idle.json
e8deba57fe293f79e1d348e44e100322f043b77b1a543d5f86fd036128140db8  incumbent-eager/post-idle.json
```

Machine-readable classification:
`data/laguna-m8-actual-offline-target-plus-draft-slot-abort-20260724.json`.
