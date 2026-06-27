# 2026-06-27T06:42Z Gate/Up Singleton-Direct Neighborhood Loss

## Question

Does the default-off verifier MoE gate/up shortcut
`LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1` become useful when paired
with the current `104.22626983476746 tok/s` record neighborhood
(`UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`)?

This is a follow-up to the earlier singleton-direct screen that was canary-clean
and near-neutral but did not beat the record. The current run uses the rebuilt
llama.cpp Gemma research stack after the direct-argmax top2 score-side-channel
cleanup, but keeps the score path disabled.

## Shared Identity

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- runtime: `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- `MTP_N_MAX=7`, backend draft sampling off, direct argmax-ID unroll 7,
  q-only assistant inputs, fused assistant output argmax, verifier backend
  argmax IDs, deferred target `h_nextn`
- selected-softmax + fused selected-softmax + weighted-sum MoE guards enabled
- route cache enabled: `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- candidate flag enabled: `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1`
- `CTX_SIZE=8192`, `BATCH_SIZE=1024`, `THREADS=8`, `POLL=100`,
  `GGML_SYCL_ENABLE_VMM=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `--ctx-checkpoints 0`
- screen depth: `CANARY_REPEATS=16` (`64` rows), `BENCH_REPEATS=2`,
  `BENCH_PROMPT_MODE=filled-long`
- headline policy: row0 only; repeated prompt rows are support-only. All rows
  reported `cached_tokens=0`.

## Results

| Run | GPU | UBATCH | n_min | p_min | Canary | Row0 tok/s after TTFT | Support mean | Decision |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-gateupdirect-ub768-nmin3-pmin010-screen-20260627T064224Z/` | 0 | 768 | 3 | 0.10 | 64/64 | 101.97728035096425 | 101.82301755599494 | loss |
| `data/gemma4-q8-gpu1-gateupdirect-ub704-nmin3-pmin010-screen-20260627T064224Z/` | 1 | 704 | 3 | 0.10 | 64/64 | 101.742204436859 | 102.77757027122725 | loss |
| `data/gemma4-q8-gpu2-gateupdirect-ub768-nmin2-pmin010-screen-20260627T064224Z/` | 2 | 768 | 2 | 0.10 | 64/64 | 103.51906816690317 | 103.57512674489695 | loss |
| `data/gemma4-q8-gpu3-gateupdirect-ub768-nmin3-pmin0136-screen-20260627T064224Z/` | 3 | 768 | 3 | 0.136 | 64/64 | 103.83774508165024 | 103.9156893148953 | loss |

Current valid record for comparison:

- `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z/`
- row0 fresh after TTFT: `104.22626983476746 tok/s`
- support mean: `104.17418893412489 tok/s`
- canary: `1536` repeats / `6144` rows
- LocalMaxxing: `cmqvv3kop0309qr013ekr8apu`

## Interpretation

The singleton-direct gate/up shortcut remains canary-clean, but it is not a
record candidate in the current neighborhood. The best row0 in this four-way
screen was only `103.83774508165024 tok/s`, below the promoted record and below
the current same-stack variance band.

Do not run full validation for this exact combination. The Gemma 26B Q8 lane
still needs a structural verifier reduction or a fresh-valid speculation change
to approach `>150 tok/s`; this patch is at most a diagnostic/default-off
experiment artifact.

## Node Profile Follow-Up

Because the first screen was close enough to be ambiguous, a short same-shape
node-profile A/B was run at `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`
with `CANARY_REPEATS=2`, `BENCH_REPEATS=1`, and `MAX_TOKENS=128`.

| Run | Canary | Row0 tok/s after TTFT | Target phase | Draft phase | Top-30 gate/up total | Top-30 down total | LM-head total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-nodeprofile-current-ub768-nmin3-pmin010-20260627T064508Z/` | 8/8 | 76.08282338746123 | `5126.065 ms / 1170 tokens = 4.381 ms/token` | `430.106 ms / 36 tokens = 11.947 ms/token` | `1694.155 ms` | `140.654 ms` | `93.849 ms` |
| `data/gemma4-q8-gpu1-nodeprofile-gateupdirect-ub768-nmin3-pmin010-20260627T064508Z/` | 8/8 | 74.8039227885777 | `5158.198 ms / 1171 tokens = 4.405 ms/token` | `432.000 ms / 36 tokens = 12.000 ms/token` | `1690.290 ms` | `138.592 ms` | `93.822 ms` |

The candidate very slightly reduced aggregate top-30 gate/up/down profile totals,
but not enough to move the target decode phase. End-to-end throughput and target
per-token time both regressed. This confirms the singleton-direct shortcut is a
real loss in the current record neighborhood, not just a noisy near-miss.
