# 2026-06-29 fused selected-softmax into selected-down VDR2

Purpose: reduce verifier MoE boundary cost by folding the selected-softmax
weight computation into the existing VDR2 reordered-Q8 selected-down
weighted-sum kernel, avoiding a separate selected-softmax weights node for
decode-small Gemma 4 MoE rows.

## Patch And Build

Source checkout:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- base commit: `c926ad098`
- build:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`

Default-off experiment flag:

```bash
LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1
```

Harness identity capture was extended in:

- `scripts/run-gemma4-26b-first-baseline.sh`
- `scripts/run-gemma4-26b-llamacpp-replica.sh`

Patch artifacts:

- source snapshot:
  `../../../../patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-fused-down-selected-softmax-current-files.patch`
- source diffstat:
  `../../../../patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-fused-down-selected-softmax-current-files.diffstat`
- harness patch:
  `../../../../patches/gemma4-26b-a4b-q8-b70/20260629-fused-down-selected-softmax-harness.patch`

The source snapshot is cumulative against upstream `c926ad098` because the
active llama.cpp checkout carries the full local Gemma record stack plus
default-off experiment paths. Do not treat it as an isolated upstream PR.

## Implementation Shape

- `llama-graph.cpp` adds
  `llama_graph_gemma4_moe_fused_down_selected_softmax_enabled()`.
- `build_moe_ffn()` may route `weights = selected_softmax_logits` into
  `ggml_moe_selected_down_weighted_sum()` when the new flag is set and the
  existing selected-down VDR2 path is otherwise eligible.
- Eligibility is intentionally decode-small only: selected experts <= 8,
  selected token rows <= 8, no warmup, no LoRA, no down bias, `w_scale == 1`,
  Q8_0 down experts, F32 contiguous activations/logits, I32 selected IDs, and
  normal selected-softmax fused path still available as fallback.
- `ggml.c` allows the selected-down op to receive either already-selected
  weights or full expert logits.
- `ggml-sycl.cpp` detects logits-shaped weights and computes the selected
  softmax into local memory once per token/row-block before the VDR2 selected
  down weighted sum. The row-boundary return stays after the local barrier so
  partial row blocks do not deadlock.

## Validation

Four strict128 lanes ran concurrently:

| GPU | Label | Flag | Primary median tok/s | p10 | mean | full tok/s median | wall tok/s median | TTFT median ms | Gate |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-fusedownselsoft2-control-strict128-20260629T1926Z` | unset | `113.94285166345176` | `103.00878916979256` | `114.14416611509836` | `112.02415698995515` | `96.36314039706488` | `177.84668551757932` | pass |
| 1 | `gemma4-q8-gpu1-fusedownselsoft2-on-strict128-20260629T1926Z` | `1` | `114.76225262049758` | `104.96241788500208` | `115.4922038699391` | `115.94792501051205` | `99.87253001641349` | `178.329226502683` | pass |
| 2 | `gemma4-q8-gpu2-fusedownselsoft2-control-strict128-20260629T1926Z` | unset | `113.96663287972905` | `102.51256487284019` | `113.59993968347561` | `111.96433603166551` | `97.04439566536016` | `177.3152929963544` | pass |
| 3 | `gemma4-q8-gpu3-fusedownselsoft2-on-strict128-20260629T1926Z` | `1` | `115.55418595150863` | `100.58380530335819` | `115.72756898779251` | `115.12076197778582` | `96.28061466190326` | `177.28512053145096` | pass |

All four runs:

- `canary_pass_all=true`;
- `canary_rows_completed=512`;
- `fresh_response_validity.valid=true`;
- `cached_tokens_all_zero=true`;
- `realistic_final_gate.passed=true`;
- target/verifier stayed `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft stayed `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`.

Paired deltas:

- GPU1 candidate minus GPU0 control: `+0.819400957045815 tok/s`.
- GPU3 candidate minus GPU2 control: `+1.5875530717795812 tok/s`.
- Candidate mean primary median: `115.1582192860031 tok/s`.
- Control mean primary median: `113.9547422715904 tok/s`.
- Mean candidate delta: `+1.203477014412698 tok/s`.

## Decision

This is a valid strict128 small positive in the intended verifier-MoE boundary,
but it is **not promoted** and was **not submitted to LocalMaxxing**:

- best candidate strict128 primary metric was `115.55418595150863 tok/s`;
- current promoted full512 record remains
  `115.8466634928202 tok/s` at
  `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`;
- strict128 is a screen, not the final full512 promotion gate.

Keep the flag and patch as a useful small mechanism. Do not spend a full512
promotion run unless a later patch stacks with it or a fresh profile shows this
node moved into the critical path enough to matter.

## Next Action

The record stack remains verifier/target-forward bound. The better next target
is a real verifier-cost reduction rather than another selected-down micro-fuse:

- exact LM-head candidate-vs-max / compact exact max design;
- row-adaptive verifier output rows;
- a bonus-token path that preserves the current bonus pipeline without adding a
  separate hot head pass;
- post-GEMM verifier MoE boundary fusion that keeps the existing fast BF16/Q8
  matmul bodies.
