# 2026-07-09 - Position-specific MTP runtime audit and compile guard

Status: **loader/runtime correctness fixes implemented; graph support pending**.
This note corrects the earlier mechanical smoke interpretation.

## Audit findings

An independent source/cache review found three blocking issues before the
position-adapter endpoint was benchmarked:

1. Adapter modules were registered as `position_adapter_down.{i}` and
   `position_adapter_up.{i}`, while candidate tensors are named
   `mtp.position_adapters.{i}.down/up.weight`. The loader would not match those
   paths and could leave uninitialized weights active.
2. `spec_step_idx` is a Python integer. vLLM's no-guard compile wrapper traced
   position 0 once and reused that graph for later positions. The prior compile
   cache contained only `position_fcs.0.weight`, proving that graph-off
   cudagraph settings alone did not disable torch compilation.
3. Optional experimental tensors were not required by the normal quantized
   loader, so a missing configured FC or adapter could be skipped rather than
   failing startup.

## Implemented correction

The focused patch is:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-position-fc-adapter-runtime-20260709.patch
```

It:

- registers `position_adapters.{i}.down/up` under the exact checkpoint module
  hierarchy;
- requires every configured position FC and adapter tensor to be present and
  loaded, and rejects unexpected position keys;
- validates non-negative counts, count coverage of `num_speculative_tokens`,
  equal FC/adapter counts, positive rank, and rank divisibility by TP size;
- disables torch compilation for Qwen3.5 MTP only when a position-specific FC
  or adapter is configured.

The ordinary checkpoint remains compiled. Experimental position candidates run
eagerly for correctness until a graph-safe depth selector exists. Static Python
compilation and `git diff --check` pass. A real rank-8 XPU train/export smoke
also passes; its compact summary is:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-position-adapter-rank8-smoke-20260709.json
```

## Consequence for earlier evidence

The earlier position-FC server smoke still proves model overlay loading, OpenAI
serving, and the fresh/cache-zero benchmark mechanics. It does **not** prove
that each compiled draft depth used a different FC: the compile cache froze
selection to position 0. Offline evaluator results are unaffected because they
execute the explicit Python step selection and were independently read back
from the candidate safetensors.

Do not promote an endpoint result from this lane until both are true:

1. an eager endpoint acceptance trace agrees directionally with the offline
   full-corpus result; and
2. position selection is tensorized or otherwise keyed into separate compiled
   graphs, then a graph-on acceptance trace matches the eager result.

The graph-safe implementation is a required performance task, not an optional
polish item: eager position dispatch cannot support the `100 tok/s` objective.
