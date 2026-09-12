## Summary

The current XPU GDN host interface assumes that every speculative step uses all
columns of the configured state-index cache. A reduced **uniform active width**
with the same maximum-capacity state-index tensor is rejected, although the
current vLLM metadata builder can retain the configured columns while producing
compact token indices. The convolution and recurrence launchers also infer their
iteration width from cache capacity, so relaxing only the assertion is insufficient.

This report is confirmed at the current-source host-contract level. No current
XPU kernel build or model run is claimed. We originally carried a related fix
in our August Qwen3.8-27B B70 builds; the kernel's newer convolution-state layout
means that historical numerical validation must not be transferred to a new patch.

## Pinned sources

- vllm-xpu-kernels: `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`
- vLLM: `22f6e4eccb674b534f62810c66838317169b6b98`

The vLLM GDN builder computes compact `spec_token_size` from actual tokens but
retains `:self.num_spec + 1` columns in `spec_state_indices_tensor`:
https://github.com/vllm-project/vllm/blob/22f6e4eccb674b534f62810c66838317169b6b98/vllm/v1/attention/backends/gdn_attn.py#L293-L308

Native `causal_conv1d_spec` requires:

```cpp
const int num_speculative_tokens = spec_state_indices_tensor.size(1) - 1;
TORCH_CHECK(spec_token == num_spec_decodes * (num_speculative_tokens + 1));
```

https://github.com/vllm-project/vllm-xpu-kernels/blob/efc85bc8a0eb3076c861b2e6cb1e1731a93905d5/csrc/xpu/gdn_attn/gdn_attn_interface.cpp#L98-L120

Both `causal_conv1d.hpp` and `gated_delta_rule.hpp` then use
`num_spec_tokens = cache_indices->size(1)` as their native iteration width.

## Concrete host-contract reproducer

- Two speculative requests (`num_spec_decodes=2`).
- Configured maximum K=2: state indices shape `[2,3]`, contiguous, valid indices.
- Active K=1 per request: four token rows, `spec_query_start_loc=[0,2,4]`,
  `spec_token_indx=[0,1,2,3]`.
- Maximum-capacity convolution state remains allocated; this is not a short
  conv-state-buffer or leading-row-padding report.

Expected: support the two active verifier rows per request while preserving the
cache row stride, or enforce/document a coherent full-width-only contract in the
caller. Actual: the host assertion evaluates `4 == 2*3` and throws. If that check
alone were bypassed, both native launch selectors would still choose width3.

A source-pinned CPU harness downloads the three exact files, verifies SHA256,
extracts the actual C++ host blocks, and compiles them with tensor-shape stubs.
It demonstrates the failure without an accelerator. The attached proof is not
execution of the full op or a current end-to-end scheduler reproduction.

https://github.com/steveseguin/b70-optimization-lab/tree/main/experiments/qwen38-27b-b70/upstream-review-20260912/width

Results:

```text
N=2, token_rows=4, cache_columns=3
upstream: interface rejects; conv width3; delta width3
candidate: interface accepts; conv width2; delta width2
```

Exact-width input remains accepted; zero, indivisible and over-capacity rows are
rejected by the candidate. The packet includes the small candidate patch as a
starting point, **not a fully validated fix**.

## What remains to validate

The simple candidate assumes uniform per-request widths; total-token divisibility
cannot establish that invariant for ragged lengths. A complete fix needs either
per-request offsets or a validated uniform contract. Please also test changing
widths (e.g. 3→2→3), previous accepted-token counts, current sliding-window conv
state semantics, mixed batches, and graph padding/capture against the reference.
No quality, performance, or deployment claim is made for the candidate.

Related #389/#391 concern graph-padded leading rows; #537 concerns mixed batches;
#544/#545 changed convolution state layout/length. None removes the above
configured-column-width equality in the pinned current source. Happy to attach
this evidence to an existing issue if the active-width limitation is tracked elsewhere.

AI assistance was used for source review, the CPU harness, and this report.
