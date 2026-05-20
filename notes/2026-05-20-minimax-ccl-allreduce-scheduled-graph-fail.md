# MiniMax M2.7 CCL_ALLREDUCE Scheduled Algorithm Graph Failure

Date: 2026-05-20

## Summary

Tested a size-ranged oneCCL `CCL_ALLREDUCE` policy against the current promoted
MiniMax M2.7 AutoRound INT4 TP4 stack:

```bash
CCL_ALLREDUCE='recursive_doubling:0-8192;ring:8193-max'
```

This was intended to check whether tiny tensor-parallel collectives could benefit
from a non-default oneCCL algorithm selection without changing model math. The
candidate did not reach token generation. It failed during XPU graph capture with:

```text
oneCCL: coll.cpp:1421 ccl_allreduce_impl: EXCEPTION: |CCL_SYCL| sched algorithms do not support sycl_graph recording, please use sycl_algorithms
```

The runner summary reports `quality_failed_raw145_n64`, but this is a startup
runtime failure before any quality output was generated. Treat it as graph/runtime
incompatibility, not as a model quality regression.

## Context

Current promoted baseline:

- Label: `minimax-moe-full-forward-customop-plus-output-ar-20260519`
- Output throughput: `89.314195` tok/s mean across four p512/n1536 repeats
- Total throughput: `119.085594` tok/s mean
- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Runtime: vLLM `0.20.1-local`, XPU, TP4, graph-enabled
- Quality: exact raw145 n64/n256, semantic, 16-repeat arithmetic, and extended sixpack all pass

Candidate delta:

```bash
CCL_ALLREDUCE='recursive_doubling:0-8192;ring:8193-max'
```

The strict runner was also updated to capture `CCL_ALLREDUCE` in
`candidate_env`, so future collective algorithm screens are reproducible.

## Result

- Status: rejected
- Quality: not reached
- Throughput: not reached
- LocalMaxxing: not submitted
- Root cause: oneCCL scheduled all-reduce algorithms are incompatible with
  `sycl_graph` capture in this graph-enabled vLLM/XPU stack.

## Evidence

The log confirms oneCCL accepted the environment variable:

```text
CCL_WARN| value of CCL_ALLREDUCE changed to be recursive_doubling:0-8192;ring:8193-max
```

It then failed inside a captured allreduce:

```text
torch.ops.vllm.all_reduce.default(buf0, 'tp:0')
RuntimeError: oneCCL: coll.cpp:1421 ccl_allreduce_impl: EXCEPTION: |CCL_SYCL| sched algorithms do not support sycl_graph recording, please use sycl_algorithms
```

Artifacts:

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-ccl-allreduce-recursive-small-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T004925Z-summary.json`
- Log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-ccl-allreduce-recursive-small-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T004925Z-quality/raw145-n64-exact.log`

## Upstream Notes

Intel oneCCL documentation describes size-ranged `CCL_ALLREDUCE` selection and
lists algorithms such as `recursive_doubling`, `ring`, and `topo`. It also notes
that `topo` is the default for GPU buffers, and that non-`topo` GPU-buffer
algorithms may copy data to host and use CPU algorithms.

Source: https://www.intel.com/content/www/us/en/docs/oneccl/developer-guide-reference/2021-15/environment-variables.html

This runtime failure adds a stronger local constraint: under graph capture, the
scheduled algorithm path is not usable in the current stack. Keep `CCL_ALLREDUCE`
unset for promoted graph-enabled runs unless a future oneCCL/XPU update provides
a graph-compatible SYCL algorithm selection path.

## Decision

Do not pursue non-`topo` `CCL_ALLREDUCE` policies for the current promoted
MiniMax TP4 graph-enabled configuration. Future communication work should focus
on either:

- preserving the default graph-compatible oneCCL/XPU path while reducing Python
  and framework boundaries around it, or
- implementing a lower-level XPU/SYCL custom collective/fusion path for the
  known small allreduce shapes rather than switching oneCCL's high-level
  scheduled algorithm table.
