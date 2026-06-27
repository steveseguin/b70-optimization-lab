# 2026-06-27T07:00Z Draft Quant Current-Stack Loss

## Question

Does a higher-precision Gemma4 MTP draft improve fresh-response throughput or
validity on the current Q8 target/verifier stack?

This rechecks the draft-quant lane after the current record stack landed:
direct argmax-ID unroll, q-only assistant inputs, fused assistant output
argmax, verifier backend argmax IDs, deferred target `h_nextn`, selected
softmax + fused selected softmax + weighted-sum MoE, and route cache.

## Shared Identity

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- runtime: `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- llama.cpp commit reported by launcher: `c926ad098`
- `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`
- backend draft sampling off, direct argmax-ID unroll 7, q-only assistant
  inputs, fused assistant output argmax, verifier backend argmax IDs, deferred
  target `h_nextn`
- selected-softmax + fused selected-softmax + weighted-sum MoE guards enabled
- route cache enabled: `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- `CTX_SIZE=8192`, `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `THREADS=8`,
  `POLL=100`, `GGML_SYCL_ENABLE_VMM=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `GGML_SYCL_DISABLE_OPT=0`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`,
  `--ctx-checkpoints 0`
- screen depth: `CANARY_REPEATS=16` (`64` rows), `BENCH_REPEATS=2`,
  `BENCH_PROMPT_MODE=filled-long`
- headline policy: row0 only; repeated prompt rows are support-only. All rows
  reported `cached_tokens=0`.

## Results

| Run | GPU | Draft | Canary | Row0 tok/s after TTFT | Support mean | Cached tokens | Decision |
| --- | ---: | --- | --- | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-draftq4km-ub768-nmin3-pmin010-screen-20260627T0700Z/` | 0 | `Q4_K_M-MTP` | 64/64 | 103.78730901696501 | 103.6419570111976 | `0,0` | loss |
| `data/gemma4-q8-gpu1-draftq5km-ub768-nmin3-pmin010-screen-20260627T0700Z/` | 1 | `Q5_K_M-MTP` | 64/64 | 103.5537767739903 | 102.50077013159739 | `0,0` | loss |
| `data/gemma4-q8-gpu2-draftq6k-ub768-nmin3-pmin010-screen-20260627T0700Z/` | 2 | `Q6_K-MTP` | 64/64 | 102.82310025564972 | 102.79483277592036 | `0,0` | loss |
| `data/gemma4-q8-gpu3-draftq80-ub768-nmin3-pmin010-screen-20260627T0700Z/` | 3 | `Q8_0-MTP` | 64/64 | 100.18260696589377 | 100.28505476470218 | `0,0` | loss |

Current valid record for comparison:

- `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z/`
- row0 fresh after TTFT: `104.22626983476746 tok/s`
- support mean: `104.17418893412489 tok/s`
- canary: `1536` repeats / `6144` rows
- LocalMaxxing: `cmqvv3kop0309qr013ekr8apu`

## Interpretation

Higher-precision MTP draft weights do not help this current stack. The best
screen in this sweep was `Q4_K_M-MTP` at `103.78730901696501 tok/s`, still
below the promoted `Q4_0-MTP` record at `104.22626983476746 tok/s`. Increasing
the draft precision monotonically worsened the row0 headline in this screen:
`Q5_K_M`, `Q6_K`, and `Q8_0` were all lower.

Do not promote or full-validate these exact draft quant variants. This
re-confirms the earlier draft-quant direction after the current stack: for the
Q8 target/verifier lane, draft quant is not the limiting factor. The next useful
Gemma work should reduce target/verifier process time or change the
fresh-valid speculation structure, not spend more runs on draft precision.
