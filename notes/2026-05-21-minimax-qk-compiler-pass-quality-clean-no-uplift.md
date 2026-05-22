# MiniMax M2.7: Q/K Compiler-Pass Retest Is Quality-Clean But No Uplift

Date: 2026-05-21

## Summary

Retested the current-stack MiniMax Q/K compiler-pass candidate:

```bash
--compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE","pass_config":{"fuse_minimax_qk_norm":true}}'
```

The candidate is quality-clean under the strict gate, but it is not a promoted
performance win. Process-level p512/n1536 throughput averaged `88.50` output
tok/s, below the public `89.31` tok/s result and below earlier in-process
warm-only measurements.

## Harness Fix

An earlier strict run failed the raw145 n64 exact hash while manual canaries
passed. The root cause was stale/inherited compile-cache state rather than a
stable model-quality regression.

The strict candidate harness now:

- avoids inheriting `VLLM_CACHE_ROOT` by default and creates a fresh strict
  cache root per labeled run;
- only reuses an inherited cache when
  `STRICT_REUSE_INHERITED_VLLM_CACHE_ROOT=1` or `CACHE_ROOT=...` is explicitly
  supplied;
- passes the promoted `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1` setting into the
  quality checker with `--qk-rms-xpu-helper`.

This prevents a stale cache from silently changing token output while still
allowing intentional cache-reuse experiments.

## Quality

Fresh-cache strict summary:

`/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-current-stack-qk-pass-freshcache-quality-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T064156Z-summary.json`

Passed checks:

- raw145 n64 exact token hash:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: PASS, arithmetic `42`, `add_one` code regexes
- arithmetic repeat: 8 greedy repeats, deterministic, exact `42`
- extended six-pack: PASS, arithmetic, code, JSON, sort, SQL

The Q/K helper flag did not change the exact token hashes.

## Throughput

Benchmark directory:

`/home/steve/bench-results/minimax-m2.7-post-repro-optimization/current-stack-qk-pass-quality-passed-bench-20260521T065829Z`

Process-level p512/n1536 output tok/s:

- `88.5678`
- `88.3653`
- `88.9364`
- `88.1116`

Mean output tok/s: `88.4953`

Mean total tok/s: `117.9937`

Output tok/s stdev: `0.3016`

## Decision

Rejected as a performance improvement. Do not submit to LocalMaxxing.

Important log clue: vLLM reported `minimax_allreduce_rms_qk op not found,
MiniMaxQKNormPass disabled`, so this was not exercising a real fused Q/K norm
kernel. The small earlier warm-only edge was measurement/cache noise, not a
meaningful optimization.

## Follow-Up

The next credible Q/K path is to implement the missing backend op or an
equivalent lower-level XPU/SYCL fusion. Another high-level compiler flag around
`fuse_minimax_qk_norm` is not enough while the op is unavailable.

Also keep tracking the CCL/pipe shutdown `Bad address` warning seen after one
quality engine exit. It did not corrupt quality artifacts here, but it remains
a reliability signal.
