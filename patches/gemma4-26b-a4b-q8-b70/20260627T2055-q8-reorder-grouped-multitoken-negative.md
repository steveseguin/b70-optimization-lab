# Gemma 4 26B Q8: Grouped Reordered-Q8 Multi-Token MoE Negative

Date: 2026-06-27

Status: valid strict-gate loss. Do not promote or submit.

Patch snapshot:

- `20260627T2055-q8-reorder-grouped-multitoken-negative.patch`
- SHA256:
  `dc7bf5774a75fa2a715dbe3f184a4522eec545149960fd0245a234a6c9185060`
- Source checkout:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`

Important patch-scope note: this patch is a snapshot against the local dirty
Gemma llama.cpp research stack, not a minimal upstream patch. The experiment
itself is the default-off flag
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1`, which adds a
reordered-Q8 counterpart to the grouped multi-token MoE path.

## Intent

The route profile showed verifier decode batches typically have small token
counts and duplicate expert hits across tokens. The hypothesis was that a
grouped reordered-Q8 path could compute each duplicate expert once per row and
scatter results back to `[row, expert_slot, token]`, avoiding repeated expert
weight reads in the VDR2 reordered path.

## Validation

Run:

- `data/gemma4-q8-gpu0-strict-vdr2-grouped-reorder-n3-p00475-ub1024-screen-20260627T205542Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-strict-vdr2-grouped-reorder-n3-p00475-ub1024-screen-20260627T205542Z.server.log`

Strict realistic gate:

- fixed realistic suite, 12 unique prompts, each prompt sent once;
- `cached_tokens=0` for every request;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram or history acceleration;
- Q8 target/verifier unchanged: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- Q4_0 MTP draft verified by target;
- chat canary: 32/32 pass.

Result:

- median tokens 1-100 after TTFT: `83.90758854375754 tok/s`;
- p10: `78.17221426541892 tok/s`;
- mean: `86.02284187160546 tok/s`;
- median full-512 after TTFT: `82.00778999411864 tok/s`;
- median wall full-512: `79.09301505839233 tok/s`;
- median TTFT: `179.04035048559308 ms`.

Current strict record at the time:

- `90.32179401019857 tok/s`;
- `data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`.

## Outcome

Valid loss, roughly `-7.1%` versus the current strict record. The likely cause
is that the grouped reordered path adds duplicate-route scans, branch/scatter
work, and register pressure that outweigh the saved duplicate expert reads for
the actual `n_tokens<=3` verifier shape.

Do not retry this exact grouped reordered-Q8 duplicate-expert approach without
new profiling evidence. If revisiting this area, measure kernel occupancy and
register pressure first, and compare against the direct VDR2 per-slot path in a
source-level microbench before spending another strict-gate run.

