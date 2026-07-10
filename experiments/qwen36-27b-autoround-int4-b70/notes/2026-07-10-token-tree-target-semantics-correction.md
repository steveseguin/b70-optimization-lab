# Qwen27 token-tree target semantics correction

Date: 2026-07-10

Status: source audit and historical-result correction; no throughput result and
no LocalMaxxing submission.

## Correction

The July 4/6 `speculative_token_tree` endpoint screens did **not** execute a
semantically valid target-side token tree for Qwen3.5/GDN. The binary-depth-2
run selected FlashAttention rather than `TREE_ATTN`, so the configured six
nodes were proposed and verified as one sequential MTP6 chain. Root-3 was
ordinary MTP3. Their measured throughput remains valid for those actual flat
shapes, but it is not evidence about the cost or correctness of tree
verification.

Even when draft `TREE_ATTN` is selected, current vLLM only uses the tree while
constructing draft candidates. Downstream target handling remains flat:

- `Scheduler` stores one flat `spec_token_ids` list;
- `GPUModelRunner._prepare_inputs()` assigns sequential token positions;
- `_calc_spec_decode_metadata()` derives linear verifier/bonus rows;
- `rejection_sample()` accepts one contiguous flat prefix;
- no target-side component consumes tree parents, depths, or leaf mappings.

The 48 GDN layers make flattening siblings specifically invalid. Their state
metadata identifies one request state slot, ReplaySSM advances one running
slot through the packed rows, and the native spec-decode kernel has no parent
map. Siblings therefore become sequential successors and contaminate one
another's recurrent state.

Primary source points in the active vLLM/XPU trees:

```text
/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py:860
/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py:1476
/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py:948
/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py:4694
/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py:7203
/home/steve/src/vllm/vllm/v1/sample/rejection_sampler.py:945
/home/steve/src/vllm/vllm/v1/attention/backends/tree_attn.py:151
/home/steve/src/vllm/vllm/v1/attention/backends/gdn_attn.py:248
/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py:3006
/home/steve/src/vllm-xpu-kernels/csrc/xpu/gdn_attn/spec_decode.hpp:5302
```

Historical log proving the binary run selected FlashAttention:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-treecurrent-binary-depth2-20260706T0700tree-20260706T0700tree/server.stdout.log
```

## Smallest valid prototype

A bounded first implementation is a greedy final-position top-2 fork:

```text
logical nodes: current, d0, d1, d2_top1, d2_top2
positions:     p,       p+1, p+2, p+3,     p+3
parents:       -,       0,   1,   2,        2
```

It uses five target rows versus four for MTP3 and still exactly one target
forward. A correct implementation needs:

1. explicit parent/depth/physical-slot metadata;
2. unique full-attention KV slots for sibling leaves and winning-slot
   promotion;
3. independent scratch GDN paths plus complete conv/SSM/ReplaySSM state fork
   and winning-state promotion;
4. a greedy tree-aware sampler and logical accepted-depth accounting;
5. tests against independent sequential execution for every branch and an
   assertion that the target runs exactly once per decode iteration.

The existing `gdn_replayssm_copy_slots` helper copies ReplaySSM ring metadata,
not the complete main checkpoint state, so it is necessary but insufficient.

## Decision for the 100 tok/s lane

Do not use the old binary row as a tree cost model, and do not implement a
post-rejection suffix regeneration that invokes the target a second time. A
final-position fork is useful correctness infrastructure but cannot by itself
remove MTP3's four-visible-token ceiling. Implement tree state machinery only
after a measured verifier-step reduction or a deeper high-acceptance draft
creates enough budget for the extra target rows.
