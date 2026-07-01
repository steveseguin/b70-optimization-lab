# Qwen3.6 Custom All-Reduce Inner Clone Required

Date: 2026-06-10

## Context

The accepted Qwen3.6 Quark W8A8 INT8 runtime uses two clone guards around
compiled XPU custom-op all-reduce:

- `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1`
- `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`

I screened whether the inner custom-op clone was redundant when the graph-side
clone remains enabled. This should have preserved model math if the graph-side
clone alone fully isolated custom-op mutation.

## Candidate

Runtime:

- Session: `qwen36-tp4-noprefix-customcloneoff-32k`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix`
- Log:
  `/tmp/qwen36-quark-int8-tp4-customcloneoff-32k-noprefix-20260610.log`
- Env delta from accepted:
  - kept `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1`
  - unset `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT`

The server loaded the accepted AOT graph cache directly. During warmup, PyTorch
warned that `vllm::all_reduce` returned an output tensor aliasing an input
tensor and that this will become an error in PyTorch 2.12. That warning was a
correct signal; the candidate was not semantically safe.

## Speed

Direct-backend p512/n512 streaming, eight measured repeats:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `99.0125` |
| e2e output tok/s | `97.8113` |
| mean client TTFT | `73.60 ms` |
| available KV cache memory | `20.7 GiB` |

Artifact:

- `data/qwen36-quark-int8-tp4-customcloneoff-single-20260610.json`

## Quality

Matched frontdoor quality failed hard against the accepted no-prefix baseline:

- exact `OK`: fail
- exact phrase copy: fail
- arithmetic canary: fail
- compact JSON: fail
- repeat stability: fail
- 8K-class long-context needle recall: fail
- baseline parity: fail

The failure was not a small deterministic drift. Outputs were corrupted token
soup, for example mixed Chinese/Latin fragments and repeated `mans` tokens in
short exact-answer prompts.

Artifact:

- `data/qwen36-quark-int8-tp4-customcloneoff-frontdoor-quality-20260610.json`

## Decision

Reject. The inner custom-op clone is required for correctness in the current
XPU custom all-reduce implementation, even when graph-side cloning remains
enabled.

The useful lesson is that the clone overhead is real enough to show a speed
signal, but removing it requires a cleaner custom-op contract that returns a
non-aliasing output or an explicitly mutating op with correct graph semantics.
Do not disable `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT` in production.
