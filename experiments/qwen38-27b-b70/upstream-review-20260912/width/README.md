# GDN dynamic active-width audit — September 12, 2026

Status: source-confirmed host contract failure on current upstream; isolated
candidate patch passes a CPU host-check regression. No current XPU build,
model execution, output comparison, or performance test was performed.

## Pinned source and reachable mismatch

- vllm-xpu-kernels: `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`.
- vLLM: `22f6e4eccb674b534f62810c66838317169b6b98`.
- Kernel file SHA256 values: `source-manifest.json`.

Current vLLM `vllm/v1/attention/backends/gdn_attn.py:293-308` creates
`spec_token_size = min(num_spec_decodes * (self.num_spec + 1), actual_tokens)`
but takes state indices with `:self.num_spec + 1` columns. The persistent
metadata allocation at lines126-129 also uses the configured maximum width.
`vllm/_xpu_ops.py:178-217` passes both tensors through to native
`gdn_attention` without narrowing the state-index columns.

For two speculative requests, configured maximum K=2 (three cache columns),
and active K=1 (two verifier tokens per request), the builder can pass four
active token indices with a `[2,3]` state-index tensor. Native
`causal_conv1d_spec` at `gdn_attn_interface.cpp:119` requires `4 == 2*3`
and throws. Independently, native convolution at `causal_conv1d.hpp:1039`
and recurrence at `gated_delta_rule.hpp:705` select three loop iterations per
request from the cache capacity instead of two from the compact buffers.
Removing only the interface assertion therefore does not repair the contract.

This is the lab's August 26 dynamic-width defect, retained in the August 28
R35 patch; the isolated candidate excludes R35's separate serial-exact path.
The source chain demonstrates a compatible mismatch. It is not a fresh
end-to-end assertion that every current dynamic scheduling configuration
reaches this shape.

## Current upstream search

On September 12, GitHub issue/PR searches for speculative GDN and dynamic GDN
found no matching active-column-width fix. Related items inspected:

- https://github.com/vllm-project/vllm-xpu-kernels/issues/389 and open
  https://github.com/vllm-project/vllm-xpu-kernels/pull/391 concern graph-padded
  **leading rows** of metadata, not configured-vs-active cache columns.
- Merged https://github.com/vllm-project/vllm-xpu-kernels/pull/537 fixes mixed
  spec/non-spec batches, not dynamic width.
- Merged https://github.com/vllm-project/vllm-xpu-kernels/pull/544 and
  https://github.com/vllm-project/vllm-xpu-kernels/pull/545 change convolution
  state layout/length; current source retains the width assertion.
- Open https://github.com/vllm-project/vllm-xpu-kernels/pull/551 changes
  convolution state writeback, not active-width selection.

Search completeness is bounded: absence of a matching result is not proof
that no maintainer has an unpublished or differently named fix.

## Candidate and CPU evidence

`active-width-candidate.patch` applies cleanly to the exact current source.
It derives uniform active width from compact Q/token buffers, checks positive
and divisible sizes and capacity bounds, and retains cache row stride. The
interface continues to require maximum-capacity convolution-state storage;
this conservative existing check is unchanged.

Run `python3 check_host_contract.py`. It downloads only the pinned three
source files, verifies hashes, extracts the exact host-check/width-selection
blocks, compiles them with `g++` against CPU tensor-shape stubs, checks patch
application, and repeats on the candidate. It does not initialize XPU.

Observed: configured width3 with two requests/four token rows is rejected by
upstream; both upstream kernel launch selectors nevertheless choose width3.
Candidate accepts and selects width2 in both kernels. Exact width3 remains
accepted. Zero, over-capacity, and indivisible compact row counts are rejected
by the candidate. Captured output is in `host-contract-result.txt`.

## Required before proposing this as a complete fix

The draft handles uniform reduced width only. Divisibility alone cannot prove
per-request uniformity: heterogeneous lengths such as [1,3] also total four.
Current native loops assume uniform width; an upstream-grade change needs a
per-request-offset implementation or an explicit validated uniform contract.

No numerical accuracy, recurrent cache correctness across changing widths,
accepted-token history, mixed batch, or graph capture result is claimed.
Current convolution state semantics changed in PR544/545 after our original
lab patch; exercise a width3→width2→width3 sequence with different prior
accepted-token counts against the reference before promoting this patch.
The public FP8 release carries the historical width patch (verified by download
and SHA256). INT4 source chains also include it, but the current R293 manifest
is draft; publication and user installation must not be inferred from local
images. This new current-upstream candidate is not deployed.

Recommendation: file the source-pinned contract bug with these bounded CPU
results and historical GPU evidence, offering the patch as an unvalidated
starting point rather than claiming a complete tested upstream fix.
