# 2026-06-27T01:16Z Current UBATCH=768 Node Profile

Purpose: profile the current Gemma 4 26B A4B Q8 one-B70 record stack after the
`UBATCH_SIZE=768` micro-record, without treating the profiling run as a
headline speed result.

Run:

- summary:
  `data/gemma4-q8-gpu0-nodeprofile-current-ub768-20260627T011603Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-nodeprofile-current-ub768-20260627T011603Z.server.log`
- diagnostic shape: `CANARY_REPEATS=2`, `BENCH_REPEATS=1`,
  `PROMPT_TOKENS=512`, `MAX_TOKENS=128`
- profiling env:
  `GGML_SYCL_NODE_PROFILE=1`, `GGML_SYCL_NODE_PROFILE_DETAIL=1`,
  `GGML_SYCL_NODE_PROFILE_EVERY=24`
- current recipe preserved: Q8 target/verifier, Q4_0 MTP draft,
  `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.136`,
  direct-unroll7 q-only assistant inputs, verifier backend argmax IDs,
  deferred target `h_nextn`, selected-softmax + weighted-sum guards,
  route cache, fused assistant output argmax, fused selected-softmax weights,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `THREADS=8`, `POLL=100`,
  `GGML_SYCL_ENABLE_VMM=0`, graph enabled, and `--ctx-checkpoints 0`.

Validity:

- chat canary passed (`8` rows);
- benchmark row had `cached_tokens=0`;
- this is **not** a promotable speed result because profiling was enabled and
  output length was `128`, not the 512-token record shape.

Observed diagnostic speed:

- `75.67683454129876 tok/s` after TTFT on the 128-token profile row;
- server timing: prompt eval `751.15 ms / 588 tokens`; eval
  `1691.17 ms / 128 tokens` (`13.21 ms/token`, `75.69 tok/s`).

Final node-profile top entries:

| Rank | Node | Total ms | Calls | Avg ms |
| ---: | --- | ---: | ---: | ---: |
| 1 | `MUL_MAT_ID:ffn_moe_gate_up-0` | `139.525` | 53 | `2.633` |
| 2 | `MUL_MAT:node_2135` (target LM head) | `93.900` | 44 | `2.134` |
| 3 | `MUL_MAT_ID:ffn_moe_gate_up-1` | `82.493` | 53 | `1.556` |
| 4 | `MUL_MAT_ID:node_60` (layer 0 MoE down) | `69.591` | 53 | `1.313` |
| 5 | `MUL_MAT_ID:ffn_moe_gate_up-8` | `68.642` | 53 | `1.295` |
| 6 | `MUL_MAT_ID:node_2119` (layer 29 MoE down) | `68.512` | 53 | `1.293` |
| 7 | `MUL_MAT_ID:ffn_moe_gate_up-2` | `68.407` | 53 | `1.291` |

Draft MTP summary from the same diagnostic:

- generated drafts / accepted drafts: `34 / 34`;
- generated draft tokens / accepted draft tokens: `235 / 187`;
- mean accepted length: `6.50`;
- acceptance rate by position:
  `(1.000, 1.000, 0.882, 0.794, 0.647, 0.588, 0.588)`;
- draft MTP timing line: `dur(b,g,a) = 0.013, 407.581, 0.349 ms`.

Interpretation:

- The UBATCH micro-record did not change the structural bottleneck: verifier
  MoE gate/up remains dominant, with the target LM head still visible.
- Existing broad paths have already been rejected: GEGLU/down matmul epilogue,
  direct fused GEGLU-down, gate/up-only fusion, broad `MUL_MAT_ID` fast paths,
  naive higher-depth MTP (`n=8..10`), and n-gram history acceleration.
- Future work should either reduce real target verifier MoE/LM-head work under
  exact greedy verification, or change the fresh-valid speculation structure.
  More scalar `p_min`, `n_max`, and runtime-shape sweeps are likely
  variance-class at best unless paired with a new mechanism.
