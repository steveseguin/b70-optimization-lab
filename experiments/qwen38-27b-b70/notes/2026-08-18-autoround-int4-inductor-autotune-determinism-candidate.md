# Qwen3.8 AutoRound INT4 Inductor autotune determinism candidate

Date: 2026-08-18

Status: **config-only candidate; not run**

## Observation

The fast native-MTP lane (`serial-exact GDN=0`, global batch invariance off)
measured `98.222` and `98.717 tok/s` from two fresh compile caches, but only
`12/25` complete outputs agreed. Reusing the first arm's compiled cache gave
`25/25` agreement and zero divergences over `12,413` tokens. The runtime is
stable for a fixed compiled artifact; fresh compilation is choosing different
artifacts.

At vLLM base `44fc8fde09fc311d3099dab10366b672d9142ea4`,
`vllm/compilation/compiler_interface.py::set_inductor_config` enables both
`max_autotune` and `coordinate_descent_tuning` for a single fixed compile
size. Their vLLM environment defaults are both `1`. Timing-driven autotuning
is therefore a concrete, testable source of fresh-cache variation.

This finding does **not** by itself validate the fast lane. A cache becomes a
valid run artifact only after its complete contents are checksum-bound,
restart-replayed, target-quality checked, and made reproducibly available.

## Required first arm

Use the exact fast-lane source/runtime/model identity and two genuinely empty,
different `VALIDATION_VLLM_CACHE_ROOT` directories. In both arms set:

```bash
export VALIDATION_INDUCTOR_MAX_AUTOTUNE=0
export VALIDATION_INDUCTOR_COORDINATE_DESCENT_TUNING=0
```

The harness records both controls in `identity.env`. Do not reuse either old
fresh-cache arm as the treatment: those used the default `1/1` policy.

Run order:

1. bounded two-prompt/smoke on empty cache A;
2. the same bounded screen on empty cache B;
3. compare complete token IDs A/B;
4. only if exact and performance is competitive, run the cache-zero cold
   25-prompt A/B suite and the Qwen3.8 target-only quality oracle;
5. restart once from a read-only copy of one sealed cache and require `25/25`
   equality again.

Report all-25 and historical selection-12 separately. The treatment must not
be called deterministic based on a single cache. A strict result also needs a
canonical relative-path file manifest for the entire selected
`VLLM_CACHE_ROOT/torch_compile_cache` subtree, plus the manifest SHA-256,
total bytes, source hashes, compiler/runtime identity, and restoration steps.

## Next split if `0/0` is slow

Run exactly two additional fresh-cache pairs, one variable at a time:

- `max_autotune=1`, `coordinate_descent=0`;
- `max_autotune=0`, `coordinate_descent=1`.

This distinguishes timing-based kernel selection from coordinate-descent
schedule changes. Do not launch a broad seed/cache harvest until these causal
arms establish which tuner creates variation. Selecting a lucky cache by
speed without first passing complete output and target-quality gates is not a
valid optimization result.
