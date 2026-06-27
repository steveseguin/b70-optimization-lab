# 2026-06-27T06:33Z Current-Stack Ubatch Neighborhood

## Question

After rebuilding the current Gemma 4 26B Q8 llama.cpp stack with the top2-score
diagnostic patch present but disabled, does a small `UBATCH_SIZE` neighborhood
around the promoted `768` recipe produce a fresh-response row0 improvement?

This is a variance/shape screen only. The target remains `>150 tok/s`; these
runs are useful only if they find a small fresh record worth promoting.

## Shared Identity

All runs used:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70 replica per GPU, `BATCH_SIZE=1024`, `THREADS=8`, `POLL=100`;
- `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, VMM off, SYCL graph on;
- current record MTP stack: `n=7`, `n_min=3`, `p_min=0.10`, direct argmax IDs,
  direct unroll 7, q-only assistant inputs, fused assistant output argmax,
  verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax
  fused, weighted sum, route cache, `--ctx-checkpoints 0`;
- score channel disabled: `MTP_DRAFT_DIRECT_ARGMAX_SCORES=0`;
- `CANARY_REPEATS=16`, `BENCH_REPEATS=2`, filled-long `512/512` shape;
- row0 headline policy with `cached_tokens=0`.

## Results

Standing record for comparison:
`data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z`,
fresh row0 `104.22626983476746 tok/s`, canary `6144/6144`.

| Run | GPU | Ubatch | Canary | Fresh Row0 Tok/s | Support Mean Tok/s | Cached |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-currentstack-ub704-screen-20260627T063346Z` | 0 | 704 | `64/64` | `103.95590849834005` | `104.01917641688385` | 0 |
| `data/gemma4-q8-gpu1-currentstack-ub768-repeat-screen-20260627T063346Z` | 1 | 768 | `64/64` | `103.63047675677204` | `104.01449482067886` | 0 |
| `data/gemma4-q8-gpu2-currentstack-ub832-screen-20260627T063346Z` | 2 | 832 | `64/64` | `101.65960657894469` | `102.69479098655364` | 0 |
| `data/gemma4-q8-gpu3-currentstack-ub896-screen-20260627T063346Z` | 3 | 896 | `64/64` | `103.94792535467161` | `103.9936897657026` | 0 |

## Decision

Status: **valid loss / no promotion**.

The rebuilt binary remains in the expected 104 tok/s class when the score
channel is disabled, but this neighborhood does not beat the promoted record.
Do not spend more budget on small ubatch-only repeats unless paired with a real
source/runtime change.
