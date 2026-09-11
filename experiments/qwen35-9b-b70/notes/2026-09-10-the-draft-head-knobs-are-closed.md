# The draft lm_head knobs are closed: the defaults are the optimum on every axis (2026-09-10)

Qwen3.5-9B W4A16, TP1, one B70 on `steve-b70s`, strict lane (FULL_DECODE_ONLY, depth 3, INT4
draft head), every arm its own mtp0 pair and mtp3 pair on fresh servers, `class_balanced_median_tok_s`
over tokens 1-100 after TTFT. Baseline for the block: d3/p0, **110.69 tok/s**. All gates 12/12 on
every arm below; nothing here changed a single output token.

| arm | knob | mtp3 pair (tok/s) | vs 110.69 |
| --- | --- | ---: | ---: |
| a5g32 | `DRAFT_LM_HEAD_INT4_GROUP_SIZE=32` | 104.75 / 104.76 | **-5.4%** |
| a5g64 | `…GROUP_SIZE=64` | 110.18 / 110.07 | -0.5% |
| (default) | `…GROUP_SIZE=128` | 110.70 / 110.63 | base |
| a18g256 | `…GROUP_SIZE=256` | 109.43 / 109.50 | **-1.1%** |
| a12dch | `…CHUNK_ROWS=1024` (default 2048) | 110.57 / 110.62 | flat |
| a17dch512 | `…CHUNK_ROWS=512` | 110.69 / 110.67 | flat |
| a15sdf32 | `…SCALE_DTYPE=fp32` (default bf16) | 110.32 / 110.29 | -0.35% |
| a8rc16 | `VLLM_XPU_FP16_LINEAR_ROWCHUNK=16` (default 32) | 110.69 / 110.66 | flat |
| a8rc64 | `…ROWCHUNK=64` | 110.90 / 110.65 | flat (noise) |
| a1g8 / a1g32 | `GDN_SPEC_GROUP=8 / 32` (default 16) | 110.70 / 110.67; 110.68 / 110.72 | flat |
| a3tight | capture sizes 1,2,3,4,5,6,8,12,16 | 110.70 / 110.69 | flat |

## What it says

- The group-size curve peaks at the default: 32 is 5.4% slower, 256 is 1.1% slower. Smaller groups
  cost scale traffic; larger ones evidently break the kernel's tile alignment. The head is
  bandwidth/alignment-bound, and no environment knob acts on that any further.
- Chunk rows, scale dtype and the target-side linear rowchunk do nothing measurable at one user.
- Two queued arms were removed unrun because their variables are read nowhere in the R276 image
  (`VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS`, `VLLM_XPU_LM_HEAD_CHUNK_ROWS`): the launchers forward
  them, the in-container check would pass, and the result would have been a clean null.
- Also closed tonight: `x32kr` passes 2K-32K identity at mtp0 and mtp3; `d2r` reproduces `d2` rung
  for rung (the leftover container never mattered).

## Two harness traps found on the way

1. The campaign harness verified every `EXTRA_ENV` knob inside the **mtp0 oracle** container too,
   and `run-server.sh` has no draft head to forward `VLLM_XPU_DRAFT_LM_HEAD_INT4_*` to, so the whole
   block aborted in ~3 min per arm. Draft-head knobs are now skipped in the mtp0 stage only.
2. `run-server.sh` never forwarded `VLLM_XPU_FP16_LINEAR_ROWCHUNK` at all, while the speculative
   launcher did with default 32; the oracle now carries it with the same default.

Single-user decode on this lane is therefore done with configuration. Anything further is a kernel:
the obvious one is a fused INT4 GEMV + argmax for the draft head, bit-exact under greedy verify.
