# 2026-06-26 Node Profile Detail Diagnostic

Purpose: identify the remaining hot nodes in the current valid Gemma 4 26B A4B
Q8 one-B70 fresh-response lane without relying on repeated-output history.

Current promoted baseline remains:

- run: `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/`
- headline: `103.2992004295621 tok/s` fresh row 0 after TTFT, `cached_tokens=0`
- validation: chat canary `1536/1536`
- LocalMaxxing: `cmqsylo2l011nqr011yydjvne`

## Runs Captured

### Current profile control

Path: `data/gemma4-q8-gpu0-current-profile-20260626T073122Z/`

- canary: `64/64`
- p512/o512 row 0: `102.3599780663357 tok/s` after TTFT, `cached_tokens=0`
- identity: current record stack with profiling enabled, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_P_MIN=0.136`, selected-softmax + weighted-sum MoE,
  draft direct argmax/unroll7, verifier backend argmax IDs, deferred target
  `h_nextn`
- conclusion: reproduces close to the promoted record, below the record by
  about 1 tok/s, useful as a profile control but not a new record

The server profile shows target verifier/model time dominates. Draft overhead is
small relative to target decode:

- draft: `draft_decode_ms=1348.637`, `draft_decodes=194`
- target: `calls=324`, `tokens=4620`, `total_ms=24225.592`
- target `process_ubatch_ms=23728.047`
- target post/extract overhead is small: `post_extract_ms=484.448`,
  `sampled_extract_ms=484.345`

### Coarse node profile

Path: `data/gemma4-q8-gpu0-nodeprofile-diagnostic-20260626T073426Z/`

- canary: `8/8`
- p512/o128 row 0: `75.68065740713982 tok/s` after TTFT, `cached_tokens=0`
- diagnostic only: node profiling disables normal graph behavior and uses
  `MAX_TOKENS=128`, so do not compare this as a headline speed result

The coarse profile identified hot anonymous nodes but could not resolve their
tensor roles. Top entries included:

- `MUL_MAT_ID:ffn_moe_gate_up-0`
- `MUL_MAT:result_output`
- `MUL_MAT:node_2255`
- `MUL_MAT_ID:ffn_moe_gate_up-1`
- `MUL_MAT_ID:node_64`
- `MUL_MAT_ID:node_2239`

### Detail node profile

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260626T0748-llamacpp-sycl-node-profile-detail.patch`

Source status: applied in
`/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`.
The patch is default-off and only adds `GGML_SYCL_NODE_PROFILE_DETAIL=1` output
to the existing `GGML_SYCL_NODE_PROFILE` path.

Path: `data/gemma4-q8-gpu0-nodeprofile-detail-20260626T074816Z/`

- canary: `8/8`
- p512/o128 row 0: `75.16764450418566 tok/s` after TTFT, `cached_tokens=0`
- diagnostic only for the same reason as the coarse node profile

Command shape:

```bash
cd /home/steve/qwen36-results-main
GGML_SYCL_NODE_PROFILE=1 GGML_SYCL_NODE_PROFILE_DETAIL=1 \
GGML_SYCL_NODE_PROFILE_EVERY=24 \
BENCH_PROMPT_MODE=filled-long CANARY_REPEATS=2 BENCH_REPEATS=1 \
PROMPT_TOKENS=512 MAX_TOKENS=128 \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.136 \
MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
scripts/run-gemma4-26b-mtp-candidate.sh
```

## Resolved Hot Nodes

Final profile snapshot at `graphs=288`:

| Rank | Node | Meaning | Total ms | Calls | Avg ms |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | `MUL_MAT_ID:ffn_moe_gate_up-0` | layer 0 MoE gate/up expert projection | 133.953 | 53 | 2.527 |
| 2 | `MUL_MAT:result_output` | assistant/draft LM head, `token_embd.weight` q6_K, hidden 1024 to vocab 262144 | 99.193 | 235 | 0.422 |
| 3 | `MUL_MAT:node_2255` | target/verifier LM head, `token_embd.weight` q8_0, hidden 2816 to vocab 262144 | 93.852 | 44 | 2.133 |
| 4 | `MUL_MAT_ID:ffn_moe_gate_up-1` | layer 1 MoE gate/up expert projection | 81.825 | 53 | 1.544 |
| 5 | `MUL_MAT_ID:node_64` | layer 0 MoE down expert projection | 70.236 | 53 | 1.325 |
| 6 | `MUL_MAT_ID:node_2239` | layer 29 MoE down expert projection | 68.605 | 53 | 1.294 |

Representative detail lines:

```text
MUL_MAT:result_output
  src0 token_embd.weight type=q6_K ne=[1024,262144,1,1]
  src1 result_norm type=f32 ne=[1024,1,1,1]

MUL_MAT:node_2255
  src0 token_embd.weight type=q8_0 ne=[2816,262144,1,1]
  src1 result_norm type=f32 ne=[2816,1,1,1]

MUL_MAT_ID:node_64
  src0 blk.0.ffn_down_exps.weight type=q8_0 ne=[704,2816,128,1]
  src1 ffn_moe_geglu-0 type=f32 ne=[704,8,2,1]
  src2 ffn_moe_topk-0 type=i32 ne=[8,2,1,1]

MUL_MAT_ID:ffn_moe_gate_up-0
  src0 blk.0.ffn_gate_up_exps.weight type=q8_0 ne=[2816,1408,128,1]
  src1 ffn_norm_2-0 type=f32 ne=[2816,1,2,1]
  src2 ffn_moe_topk-0 type=i32 ne=[8,2,1,1]
```

## Interpretation

The anonymous nodes are no longer mysterious:

- `node_2255` is the target/verifier LM head.
- `result_output` is the assistant/draft LM head.
- `node_64`, `node_139`, and `node_2239` are MoE down projections, not router
  materialization or hidden state handoff nodes.
- `ffn_moe_gate_up-*` remains the largest per-layer verifier cost. MoE down
  projections are also hot.

This steers future work away from already-tested weak lanes:

- Do not rerun fused output argmax as-is; prior attempts were neutral/slower,
  and this profile only confirms the LM head is hot, not that the existing
  fusion approach works.
- Do not rerun the selected-softmax/weighted-sum p-min/thread/runtime sweeps
  without a new mechanism; they are already near the current record.
- Do not rerun the broad or filtered `MUL_MAT_ID` fast-path patches as-is;
  previous gate-up and down variants regressed or landed below record.
- Do not rerun device-H handoff, fused-down, fused GEGLU-down, skip-early
  expert weights, or sampled extraction without a materially different design.

## Next Plausible Lanes

The useful next patches need to change the structure, not just retune knobs:

1. Verifier-specific LM-head reduction for greedy validation. The target LM
   head is hot (`node_2255`). A safe implementation cannot merely compute the
   drafted candidate logit because that does not prove greedy argmax, but a
   verifier-only top-1/top-k path or bounded comparison may be worth a source
   audit. Any result must preserve fresh-response canaries and cannot be
   promoted without full validation.
2. Router/materialization fusion before MoE matmuls. The profile shows the
   matmuls dominate, but a deeper graph-level change that removes intermediate
   selected-weight/top-k materialization may be materially different from the
   rejected broad `MUL_MAT_ID` kernel toggles.
3. A targeted MoE gate/up schedule for exactly `ne=[1408,8,2,1]`,
   `src0=q8_0 [2816,1408,128,1]`, `src1=f32 [2816,1,2,1]`, `src2=i32 [8,2]`.
   This must be a shape-specific kernel/scheduling change, not the prior broad
   multi-token `MUL_MAT_ID` fast path.

## Validity

These profiler runs are fresh-response diagnostics (`cached_tokens=0`) but are
not headline records. Node profiling and the o128 shape change runtime behavior
and lower throughput; use them only to guide source work. The promoted headline
remains the 1536-row canary result at `103.2992004295621 tok/s`.
