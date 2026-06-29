# 2026-06-29 FA-on 32K/VMM Node Profile

Status: diagnostic only. Do not submit or promote this row.

## Run Identity

- label: `gemma4-q8-gpu0-faon-vmm-ctx32768-nodeprofile-20260629T213530Z`
- summary:
  `data/gemma4-q8-gpu0-faon-vmm-ctx32768-nodeprofile-20260629T213530Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-faon-vmm-ctx32768-nodeprofile-20260629T213530Z.server.log`
- target/verifier: UD-Q8_K_XL Gemma 4 26B A4B IT
- draft: Q4_0 MTP, `n_max=3`, `n_min=2`, `p_min=0.0475`
- runtime: llama.cpp `c926ad098`, one B70, `FLASH_ATTN=on`,
  `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`, f16 KV,
  `UBATCH_SIZE=1024`, `--ctx-checkpoints 0`
- profiling: `LLAMA_SERVER_SPEC_PROFILE=1`, `LLAMA_MTP_DRAFT_PROFILE=1`,
  `GGML_SYCL_NODE_PROFILE=1`, `GGML_SYCL_NODE_PROFILE_DETAIL=1`,
  `GGML_SYCL_NODE_PROFILE_EVERY=24`

## Validity

The fixed realistic gate passed and every request had `cached_tokens=0`, but
the profiler perturbs timing heavily. Treat the throughput below as profiler
overhead, not headline speed.

- canary: 256 rows, pass
- realistic gate: pass, fresh-response classification
- cached tokens: all zero
- profiler-perturbed median tokens 1-100 after TTFT:
  `73.0624227983514 tok/s`
- p10: `70.63685566250544 tok/s`
- mean: `74.93505076362815 tok/s`
- median full-output after TTFT: `72.91389765200056 tok/s`
- median wall full-output: `65.26724506076545 tok/s`
- median TTFT: `198.22218449553475 ms`

The current valid headline remains the same-identity non-profiled record:
`117.91456485086059 tok/s` from
`data/gemma4-q8-gpu3-faon-vmm-ctx32768-full512-20260629T211437Z/summary.json`.

## Profile Findings

The final SYCL node profile reported `graphs=5688`, `unique_nodes=1478`, top 30
nodes. The hot path is target/verifier compute, not sampling or host overhead.

Top nodes:

| Rank | Node | Total ms | Calls | Avg ms | Shape / note |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | `MUL_MAT:node_1775` | 1769.820 | 1295 | 1.367 | Q8_0 LM head, `token_embd.weight`, `ne=[262144,1,1,1]` |
| 2 | `MUL_MAT_ID:ffn_moe_gate_up-29` | 1124.115 | 1831 | 0.614 | final routed gate/up, BF16 expert weights |
| 3 | `MUL_MAT_ID:ffn_moe_gate_up-0` | 823.636 | 1831 | 0.450 | routed gate/up, Q8_0 expert weights |
| 4-30 | `MUL_MAT_ID:ffn_moe_gate_up-*` | 792.760 to 695.754 | 1831 | 0.433 to 0.380 | routed gate/up layers, Q8_0 expert weights |

All detailed `token_embd.weight` LM-head profile rows in this run are
one-column (`ne=[262144,1,1,1]`). That matters because the existing Q8 MMVQ
multi-column dispatch already has reordered `src1_ncols <= 8` handling, but it
does not apply to this one-column LM-head hotspot.

Server profile:

| Phase | Time ms | Calls | Tokens | Avg ms | Avg token |
| --- | ---: | ---: | ---: | ---: | ---: |
| draft | 6471.396 | 1833 | 3840 | 3.530 | n/a |
| target decode | 81326.913 | 1833 | 15936 | 44.368 | 5.103 |
| target prompt | 42291.085 | 536 | 10799 | 78.901 | 3.916 |
| target generation | 39035.828 | 1297 | 5137 | 30.097 | 7.599 |
| process | 43.657 | n/a | n/a | n/a | n/a |
| sample accept | 3.850 | n/a | n/a | n/a | n/a |
| common accept | 12.970 | n/a | n/a | n/a | n/a |
| emit | 3.728 | n/a | n/a | n/a | n/a |

MTP profile:

- `process_tokens=15936`
- `verify_rows=15936`
- draft decode phase: about `6484 ms`
- target decode phase: about `81325 ms`

## Decision

Do not keep testing host-side sampler, copy, or n-gram/history shortcuts as
record candidates. The remaining record work needs source-level target/verifier
compute reduction that preserves exact target verification.

Do not retest the old `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS` idea as written. That
experiment targeted multi-column Q8 MMVQ x-block reuse and already lost in
`20260627T1315-q8-mmvq-small-ncols-reuse-x-negative.md`; the latest profile
shows the leading LM-head node is one-column, while the source already has Q8_0
reordered multi-column dispatch for `src1_ncols > 1 && src1_ncols <= 8`.

Current useful source directions:

1. Reduce one-column Q8 LM-head verifier cost without falling back to the
   slower `MUL_MAT_ARGMAX` implementations already closed as negative.
2. Reduce routed MoE gate/up cost while preserving the current fast VDR2 Q8
   reordered path; direct BF16 and GEGLU/down fusion variants already lost.
3. Treat any new idea as a strict A/B: two same-window controls, two flag-on
   lanes, fixed realistic gate, cold prompts only, `cached_tokens=0`, and no
   LocalMaxxing submission unless a full512 promotion beats `117.91456485086059`.
