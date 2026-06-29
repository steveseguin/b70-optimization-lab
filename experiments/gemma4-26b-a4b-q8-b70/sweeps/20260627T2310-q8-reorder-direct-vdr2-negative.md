# 2026-06-27T2310 - Q8 Reorder Direct VDR2 Negative

## Question

Can the active Gemma 4 26B verifier `MUL_MAT_ID` path improve by replacing the
generic reordered-Q8 MMVQ trait/addressing path with a direct Q8_0/VDR2
specialization?

The active node profile shows `ffn_moe_gate_up-*` verifier nodes with
`ids ne=[8,2]` and `src1 ne=[2816,1,2,1]`, so the relevant shape is top-8
routes across a tiny multi-token verifier batch. This is the real shape the
earlier pair-slot experiment missed.

## Patch

Default-off source patch in
`/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- `ggml/src/ggml-sycl/mmvq.cpp`: add direct VDR2 Q8_0 reordered
  `MUL_MAT_ID` kernel and wrapper
  `ggml_sycl_mul_mat_vec_q_id_multi_token_direct_vdr2_q8_0_reorder()`;
- `ggml/src/ggml-sycl/mmvq.hpp`: declare the wrapper;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: add env
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`, dispatch, and graph
  eligibility for `src0=Q8_0`, reordered, `ne11=1`, `n_experts_used<=8`.

Build:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 \
  --target llama-server -j 8
```

The first build failed because the direct kernel assumed `WARP_SIZE=32`.
The B70 VDR2 build uses `GGML_SYCL_WARP_SIZE=16`, so the VDR2 subgroup block
stride is `4`, not `8`. The patch was corrected to use the generic reordered
kernel's positive invariant instead of a hard-coded `8`.

## Runs

All runs used the strict fresh-response realistic suite:

- each prompt sent once;
- all `cached_tokens=0`;
- no n-gram/history acceleration, prompt reuse, response reuse, or context
  checkpoints;
- target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- VDR2 record identity: `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, f16 KV, `--ctx-checkpoints 0`.

Screen:

- `data/gemma4-q8-gpu0-directvdr2-screen-n3-nmin2-p00475-ub1024-20260627T230753Z/summary.json`
- canary: 16 repeats / 64 rows, pass;
- realistic gate: pass, all `cached_tokens=0`;
- median tokens 1-100 after TTFT: `90.71249998925582 tok/s`;
- p10 `82.6145921361124`, mean `91.20552151293003`;
- median full-512 after TTFT `87.19383550886401`, wall full-512
  `84.31754316931735`.

Four-GPU confirmation batch:

| GPU | Result path | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-directvdr2-confirm-n3-nmin2-p00475-ub1024-20260627T231054Z/summary.json` | `89.78446476095618` | `79.9875872769949` | `88.21500291621096` | `85.42881610612889` |
| 1 | `data/gemma4-q8-gpu1-directvdr2-confirm-n3-nmin2-p00475-ub1024-20260627T231054Z/summary.json` | `88.2181491417087` | `78.024728224439` | `88.44314351951004` | `85.45767579062687` |
| 2 | `data/gemma4-q8-gpu2-directvdr2-confirm-n3-nmin2-p00475-ub1024-20260627T231054Z/summary.json` | `86.62953234681859` | `75.57863642779463` | `85.7732305347243` | `82.5024118270705` |
| 3 | `data/gemma4-q8-gpu3-directvdr2-confirm-n3-nmin2-p00475-ub1024-20260627T231054Z/summary.json` | `86.36862208450489` | `77.39926641311989` | `87.14222078166824` | `83.50476279505727` |

All four confirmation rows passed canaries and the realistic final gate.

## Decision

Negative. Do not submit to LocalMaxxing.

The current promoted record remains `90.98312252660529 tok/s` from
`data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`.
The direct VDR2 screen was record-adjacent but did not confirm. The dedicated
direct Q8_0/VDR2 addressing likely does not overcome compiler scheduling,
register allocation, or generic-path optimization already achieved by the
trait-based reordered kernel.

Keep the patch default-off as a source artifact. Do not promote it into a
record recipe unless a later profile shows it improves a different shape.

## Next

Small `MUL_MAT_ID` addressing cleanups are now low ROI. Better Gemma candidates:

- reduce verifier MoE/down/weighted-sum boundary work;
- avoid full verifier LM-head work with an exact candidate-vs-max proof;
- improve fresh-valid draft acceptance without repeated-output history.
