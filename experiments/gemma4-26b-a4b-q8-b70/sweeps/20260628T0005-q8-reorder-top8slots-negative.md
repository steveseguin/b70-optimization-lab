# 2026-06-28: Q8 Reorder Top-8 Slots Negative

## Question

Can the active Gemma 4 26B verifier MoE shape benefit from computing all eight
selected expert slots for a token/row in one reordered-Q8 workgroup?

The active strict recipe routes through `MUL_MAT_ID` with Q8_0 expert weights,
`ids ne=[8,2]`, and `src1 ne=[2816,1,2,1]`. Prior direct and grouped
reordered-Q8 attempts suggested the generic path still had overhead, so this
test tried reusing the quantized activation row across all eight selected
experts instead of launching one slot at a time.

## Patch / Toggle

Default-off source path in
`/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- `ggml/src/ggml-sycl/mmvq.cpp`:
  `ggml_sycl_mul_mat_vec_q_id_multi_token_top8_slots_q8_0_reorder()`;
- `ggml/src/ggml-sycl/mmvq.hpp`: declaration and rationale comment;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: env gate and dispatch;
- env: `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS=1`.

Harness identity logging was added to:

- `scripts/run-gemma4-26b-llamacpp-replica.sh`;
- `scripts/run-gemma4-26b-first-baseline.sh`.

The VDR2 build succeeded with the patch present. The path is default-off.

## Validation Shape

All four lanes used the current promoted strict identity except for the new env
toggle:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- llama.cpp commit: `c926ad098`;
- build: reordered-Q8 VDR2;
- speculation: `n_max=3`, `n_min=2`, `p_min=0.0475`;
- `UBATCH_SIZE=1024`, `BATCH_SIZE=1024`, `ctx=8192`;
- `--ctx-checkpoints 0`, no cache/history reuse;
- fixed realistic suite, each prompt once, `cached_tokens=0`.

## Results

| GPU | Result path | Gate | Median tok/s 1-100 after TTFT | p10 | Mean | Full-512 after TTFT | Wall full-512 | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-top8slots-vdr2-strict-n3-nmin2-p00475-ub1024-20260628T000451Z/summary.json` | pass | `91.45707162294053` | `78.20620127526067` | `88.93210502337007` | `83.43971833952776` | `80.97269893284786` | `181.22055451385677` |
| 1 | `data/gemma4-q8-gpu1-top8slots-vdr2-strict-n3-nmin2-p00475-ub1024-20260628T000542Z/summary.json` | pass | `88.36905349287005` | `77.6331374063482` | `88.03118242242329` | `84.08612429789025` | `81.68391230069983` | `180.03749649506062` |
| 2 | `data/gemma4-q8-gpu2-top8slots-vdr2-strict-n3-nmin2-p00475-ub1024-20260628T000542Z/summary.json` | pass | `87.57423762721632` | `78.52837357200801` | `87.4545728865836` | `84.1077617108782` | `81.74138124145765` | `181.4050620305352` |
| 3 | `data/gemma4-q8-gpu3-top8slots-vdr2-strict-n3-nmin2-p00475-ub1024-20260628T000542Z/summary.json` | pass | `86.84604657306411` | `80.45742422311872` | `88.36776694086528` | `83.4922416463333` | `80.85292143325506` | `180.97777350340039` |

Current promoted record for comparison:
`90.98312252660529 tok/s` from
`data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`.

## Decision

Negative. Do not submit to LocalMaxxing and do not include this env in promoted
reproduction commands.

The GPU0 row is a valid high observation, but the four-lane center is below the
current record and below the VDR2 confirmation family. The likely explanation
is that sharing the activation row across all eight slots increases register
and private-memory pressure enough to offset the saved activation loads.

## Follow-Up

Do not continue this exact top-8 slot-blocked kernel without lower-level
evidence from a kernel profile. The next high-ROI Gemma work should target
structural verifier cost: LM-head / argmax work, verifier MoE reduction, or a
fresh-valid speculation mechanism. Small reordered-Q8 addressing variants
(`pair_slots`, `direct_vdr2`, `top8_slots`, grouped) have now all failed to
beat the strict cold-suite record.
