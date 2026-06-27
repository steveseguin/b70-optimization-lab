# 2026-06-27: Reordered-Q8 Grouped Multi-Token MoE Negative

Status: valid strict realistic-suite loss. Do not promote or submit to
LocalMaxxing.

## Context

Current strict record:

- `90.32179401019857 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- run:
  `../../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`;
- one B70, llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  VDR2 reordered Q8 MoE-ID, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `cached_tokens=0` for every request.

This experiment kept the same record-family launch identity and added the
default-off source flag
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1`.

## Patch

Saved under:

- `../../patches/gemma4-26b-a4b-q8-b70/20260627T2055-q8-reorder-grouped-multitoken-negative.patch`;
- `../../patches/gemma4-26b-a4b-q8-b70/20260627T2055-q8-reorder-grouped-multitoken-negative.md`.

The patch snapshot is against the local dirty llama.cpp Gemma research stack.
It is not a minimal upstream patch. The specific experiment adds a grouped
multi-token reordered-Q8 MoE path and activates it only with
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1`.

Note: the run happened before the harness identity patch for this new flag, so
`summary.json` does not contain
`launcher_identity.llama_sycl_mul_mat_id_multi_token_grouped_q8_0_reorder`.
The command/server log and patch artifact identify the tested flag. The harness
now captures it for future runs.

## Result

Run:

- `../../data/gemma4-q8-gpu0-strict-vdr2-grouped-reorder-n3-p00475-ub1024-screen-20260627T205542Z/summary.json`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-strict-vdr2-grouped-reorder-n3-p00475-ub1024-screen-20260627T205542Z.server.log`.

Validity:

- strict realistic final gate passed;
- fixed realistic suite, 12 unique prompts, each prompt once;
- `cached_tokens=0` on every request;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram/history acceleration;
- Q8 target/verifier unchanged;
- target-model verified MTP acceptance;
- chat canary 32/32 pass.

Metrics:

| Metric | Value |
| --- | ---: |
| median tok/s, tokens 1-100 after TTFT | `83.90758854375754` |
| p10 tok/s, tokens 1-100 after TTFT | `78.17221426541892` |
| mean tok/s, tokens 1-100 after TTFT | `86.02284187160546` |
| median full-512 after TTFT | `82.00778999411864` |
| median wall full-512 | `79.09301505839233` |
| median TTFT | `179.04035048559308 ms` |

## Conclusion

The idea lost despite being valid. The route profile correctly showed duplicate
expert hits, but grouping them in the reordered-Q8 path appears to add more
branch/scatter/register pressure than it saves at the strict `n_max=3` verifier
shape. Do not repeat this exact path without a lower-level kernel profile that
shows the grouping overhead can be removed.

Next higher-signal work should target verifier-side structural cost that affects
fresh responses directly: target LM-head/output selection, draft acceptance
quality that raises accepted tokens without history reuse, or a tighter
source-level profile of the VDR2 verifier step before writing another MoE
kernel variant.

