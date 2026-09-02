# Qwen3.8 Flash-Next EP4 M1 sparse assignment XPU design — deferred

Date: 2026-09-01
Status: design retained; XPU implementation and gate deferred

## Priority correction

The complete replaceable region remains small, although it is larger than the
initial alignment-only accounting. A28 attributes about `0.240581 ms/token` to the 48
`moe_align_block_size` calls and `0.043295 ms/token` to their associated sort,
or `0.283876 ms/token` in total. Against the approximately `181.30 ms` target
step, deleting the entire region would have only a `~0.157%` mechanical
endpoint ceiling. The separately preserved CPU candidate remains useful
bookkeeping evidence, but an XPU implementation is deferred behind the W13-N32
MoE and HC gate-mix candidates, which have materially larger plausible value.

No XPU API, compiler, model, endpoint, or GPU was invoked for this addendum.
Live vLLM and `vllm-xpu-kernels` are unchanged.

## Retained native design

If later profile evidence makes this region important, the next candidate
should be an experiment-local native SYCL extension, not a chain of Python
Torch operations. The latter would allocate intermediates and launch several
operators to replace one small native operation, so it is not a credible
runtime treatment even if a component graph could capture it.

The frozen native constraints are:

- dispatch only for exact `M=1`, `top_k=10`, `num_experts=512`,
  `BLOCK_SIZE_M=16`, EP4 mapped execution with
  `ignore_invalid_experts=True`, behind a default-off environment selector;
  reject or fall through before the generic cumsum workspace is allocated;
- one in-order-queue submission, one workgroup, and 32 work-items; no host
  tensor reads, synchronizations, or per-call allocations;
- bounds-check every selected global ID before indexing the 512-entry expert
  map; negative, padding, and out-of-range IDs must be ignored exactly as by
  the generic authority;
- accept the general map contract, not only contiguous rank maps: map global
  IDs to local IDs, discard any mapped value below `0` or at least `512`, and
  order active blocks by ascending mapped-local ID;
- coalesce duplicate selected IDs for the same mapped local expert into one
  padded expert block. The candidate may retain flattened token-position order,
  but the generic atomic path does not expose duplicate ordering as a stable
  byte contract; a ten-entry sort that emits one block per selection is still
  incorrect when routes repeat;
- initialize all 160 `sorted_token_ids` entries to sentinel `10`, all ten
  `expert_ids` entries to the generic inactive sentinel `0`, and set
  `num_tokens_post_pad` to `16 * unique_valid_local_experts`;
- preserve the generic operator for every non-exact shape and for any rejected
  metadata contract.

## Required future gate

Any resumed implementation must remain source-bound and isolated from the live
runtime until qualification. Its one-B70 gate must require the fixed current-
boot root-NVMe clearance receipt and explicit authorization, bind the A28
profile plus current vLLM/kernel/native-library identities, use no full model
or endpoint, and publish checksummed evidence without overwrite.

Correctness must cover all four contiguous production maps plus permuted valid
maps; changing routes; 0/1/5/10-local-hit routes; negative, padding, and
out-of-range selected IDs; duplicate local experts; exact eager and captured
bytes for all three outputs on production-unique routes; duplicate grouping,
token membership, padding, and count without assuming generic atomic order;
unchanged inputs; and the generic native operator as authority. Timing must use
a matched `control/candidate/candidate/control` bracket in fresh processes
because the default-off selector is resolved before graph capture, and report
each EP rank separately. Even a positive component result must not advance to
an endpoint arm unless a fresh target-step profile shows a meaningful endpoint
ceiling.
