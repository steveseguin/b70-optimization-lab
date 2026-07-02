# Gemma 4 26B Q8: Record-Stack Node Profile Hotspots

Date: 2026-07-02

## Purpose

Refresh the profiler view on the current Gemma 4 26B A4B Q8 record stack after
the recent closed verifier and service lanes. The goal was to identify the next
non-roulette code target for short-context decode without changing the promoted
quality lane.

This is a **diagnostic-only** run. It passed the fixed cold gate, but
`GGML_SYCL_NODE_PROFILE=1` disables SYCL graph execution in the runtime and the
run used `MAX_TOKENS=128`, so its throughput must not be submitted or treated
as a headline result.

## Command

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19110 \
LABEL=gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z \
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 \
MAX_TOKENS=128 CANARY_REPEATS=4 \
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 READINESS_TIMEOUT_S=900 \
LLAMA_MTP_DRAFT_PROFILE=1 LLAMA_SERVER_SPEC_PROFILE=1 \
LLAMA_SPEC_VERIFY_SYNC_PROFILE=1 \
GGML_SYCL_NODE_PROFILE=1 GGML_SYCL_NODE_PROFILE_EVERY=100 \
GGML_SYCL_NODE_PROFILE_DETAIL=1 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Evidence:

- `data/gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z/summary.json`
- `data/gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z/realistic-suite.json`
- `data/gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z/chat-canary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z.server.log`

## Validity

- fixed realistic prompt suite, each prompt once as a cold response
- `cached_tokens=0` for every suite prompt
- no prompt cache, context checkpoint, response reuse, n-gram/history
  acceleration, or warmed repeated prompt averaging
- UD-Q8_K_XL target/verifier unchanged; Q4_0 MTP draft only
- canary: `16/16` rows pass
- realistic final gate: pass

Diagnostic caveat:

- The summary's policy fields classify the run as fresh-response because the
  fixed suite and cache rules were respected.
- Do **not** promote or submit the speed number: node profiling changes runtime
  behavior by disabling graph execution, and this run did not measure the
  full512 reporting window used for record submissions.

## Metrics

Primary metric, generated tokens 1-100 after TTFT:

- median: `76.92766796910604 tok/s`
- p10: `73.68771766598842 tok/s`
- mean: `78.07406356814731 tok/s`

Full generated output after TTFT:

- median: `77.90616956017679 tok/s`
- p10: `72.9159488995737 tok/s`
- mean: `78.44263886932814 tok/s`

Wall-clock full-output throughput:

- median: `69.82528714636383 tok/s`
- p10: `64.39860986513233 tok/s`
- mean: `69.5368321924693 tok/s`

TTFT:

- median: `197.82511657103896 ms`
- p10: `192.68981229979545 ms`
- mean: `209.0033857675735 ms`

Decision: **diagnostic only / no record**. The current valid record remains
`124.97714084813418 tok/s` from
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

## Node Profile Hotspots

Final cumulative node-profile block:

- `graphs=2400`
- `unique_nodes=1423`
- top rows below are from the final `top=30` block

| Rank | Total ms | Calls | Avg ms | Node |
| ---: | ---: | ---: | ---: | --- |
| 1 | `817.753` | `591` | `1.384` | `MUL_MAT:node_1715` |
| 2 | `372.032` | `647` | `0.575` | `MUL_MAT_ID:ffn_moe_gate_up-29` |
| 3 | `240.491` | `584` | `0.412` | `MUL_MAT_ARGMAX:mtp_direct_argmax_unroll_token_0` |
| 4 | `238.944` | `584` | `0.409` | `MUL_MAT_ARGMAX:mtp_direct_argmax_unroll_token_1` |
| 5 | `238.825` | `584` | `0.409` | `MUL_MAT_ARGMAX:mtp_direct_argmax_unroll_token_2` |
| 6 | `214.562` | `647` | `0.332` | `MUL_MAT_ID:ffn_moe_gate_up-0` |
| 7 | `210.405` | `647` | `0.325` | `MUL_MAT_ID:ffn_moe_gate_up-1` |
| 8 | `206.061` | `647` | `0.318` | `MUL_MAT_ID:ffn_moe_gate_up-2` |
| 9 | `205.184` | `647` | `0.317` | `MUL_MAT_ID:ffn_moe_gate_up-27` |
| 10 | `202.647` | `647` | `0.313` | `MUL_MAT_ID:ffn_moe_gate_up-7` |

The top `MUL_MAT:node_1715` detail line identifies the target/verifier
full-vocabulary LM head:

```text
Q8_0 token_embd.weight [2816,262144] x GET_ROWS:result_norm
```

The three separate draft nodes are MTP draft direct-argmax LM-head work for the
unrolled draft positions. Log detail shows these use `q6_K` output weights:

```text
src0{NONE:token_embd.weight type=q6_K ne=[1024,262144,1,1]}
src1{MUL:result_norm type=f32 ne=[1024,1,1,1]}
```

Together they are roughly the same profile scale as the target verifier LM-head
node in this diagnostic mode.

## Server / MTP Profile

Final cumulative profile lines:

- target decode phase:
  `calls=669`, `tokens=3915`, `total_ms=23119.715`,
  `per_call_ms=34.559`, `per_token_ms=5.905`,
  `process_ubatch_ms=23096.500`
- draft decode phase:
  `calls=607`, `tokens=608`, `total_ms=3042.254`,
  `per_call_ms=5.012`, `per_token_ms=5.004`,
  `process_ubatch_ms=3029.653`
- MTP draft profile:
  `process_calls=669`, `process_tokens=3915`, `verify_rows=3915`,
  `draft_decodes=606`, `draft_decode_tokens=606`,
  `fast_topk_calls=606`, `vocab_scanned=0`, `sampler_calls=0`
- spec verify sync profile:
  `calls=512`, `rows=2042`, `sync_ms=0.394`,
  `avg_call_ms=0.001`

Interpretation:

- Host bookkeeping, sampler work, accept/copy accounting, and verifier sync
  are too small to be current record levers.
- The remaining short-decode cost is graph/backend compute: target verifier
  LM-head, draft argmax LM-head, and MoE gate-up `MUL_MAT_ID`.
- The older row-by-row accept-prefix verifier variants are closed because they
  serially add LM-head launches. Any future verifier work must be non-serial
  and exact.

## Next Credible Lanes

1. **Draft argmax batching/fusion is not a simple win.**
   Source audit after the profile found the backend already supports
   multi-column `MUL_MAT_ARGMAX`, but these three unrolled draft heads are
   autoregressive: token 0 feeds draft step 1, and token 1 feeds draft step 2.
   They cannot be represented as one independent multi-column argmax without
   changing the draft algorithm. Existing `MUL_MAT_ARGMAX` tile/reorder/
   multi-reuse knobs also have prior negative coverage. A current-record
   full512 A/B of `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` on the draft
   path passed all gates but did not win (paired median-ratio CI
   `-2.594% / +0.001% / +4.021%`). Future draft-side work should target a new
   single-node `q6_K` argmax kernel design or a different draft algorithm, not
   a naive batch of `mtp_direct_argmax_unroll_token_0/1/2` or another
   tile-subgroup retest. Evidence:
   `20260702-argmaxtile16-draft-q6k-no-win.md`.

2. **Exact verifier LM-head reduction, only if non-serial.**
   The target/verifier LM-head is still rank 1, but prior audits show a simple
   row-by-row accept-prefix design loses badly. Reopen only for a true backend
   row-adaptive op or a mathematically sound candidate-bound certificate that
   avoids full-vocab work while preserving exact target verification and the
   full-match bonus row.

3. **MoE gate-up only with a new structural idea.**
   Many `ffn_moe_gate_up-*` nodes remain hot, but previous MoE selected-down,
   gate-up, rowpack, grouped, and epilogue attempts already closed most easy
   variants. Do not reopen MoE config roulette without a concrete source-level
   design.

No LocalMaxxing submission was made from this run.
