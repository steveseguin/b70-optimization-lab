# 2026-07-09 - Position-specific MTP runtime audit and compile guard

Status: **loader/runtime fixes plus graph specialization implemented; endpoint
validation pending**. This note corrects the earlier mechanical smoke
interpretation.

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
- opts the position-specific Qwen3.5 MTP lane into a narrowly preserved
  `spec_step_idx` constant guard. vLLM still drops unrelated guards, but
  torch.compile now creates and caches one optimized graph per draft depth
  instead of silently reusing depth 0;
- automatically falls back to eager for this opt-in mode when AOT compile or
  the bytecode hook is active, because those modes cannot safely recompile by
  depth yet.

The ordinary checkpoint remains on the unchanged no-guard compile behavior.
The generic guard-preservation capability is default-inert and covered by a
test that selects depths `0,1,2,1,0` through one `ModuleList`; all outputs use
the correct cached specialization. `tests/compile/test_wrapper.py` passes in
full (`3 passed`). Static Python compilation and `git diff --check` also pass.
A real rank-8 XPU train/export smoke passes; its compact summary is:

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
2. the new per-depth graph specialization produces the same acceptance trace
   graph-on and the compile/capture logs show every configured depth.

The compile-wrapper unit proves the dispatch mechanism, not Qwen endpoint
capture. A real candidate must still prove weight loading, five specializations,
capture/replay, and acceptance parity before performance is trusted.
