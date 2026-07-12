# 2026-07-12 DFlash + MTP Q4_0 Initial Benchmark

## Setup

- Target: `unsloth/Qwen3.6-27B-MTP-GGUF:Q4_0` (16.1 GB)
- Draft (DFlash): `Alittlehammmer/Qwen3.6-27B-DFlash-GGUF-llama.cpp:Q4_K_M` (1.03 GB)
- Build: llama.cpp `e3546c794` (9976), SYCL, B70 `bmg-g31`, NDEBUG, #25063 present
- Hardware: single Intel Arc Pro B70 per test, Q8 KV cache, `-fa on`, `-sm layer`
- Prompts: code ("write prime checker") + chat ("explain database index")
- Temperature 0.0, max_tokens 128, warm (second prompt per server)

## Results

| Config | Code tok/s | Chat tok/s | Code Acceptance | Chat Acceptance | Code Mean Len |
|--------|:---:|:---:|:---:|:---:|:---:|
| no-spec (llama-bench) | 26.58 | 26.58 | — | — | — |
| **MTP3** | **53.32** | **58.34** | 0.731 | 0.833 | 3.17 |
| DFlash n_max=3 | 51.06 | 55.37 | 0.717 | 0.752 | 3.10 |
| DFlash n_max=5 | 56.37 | 53.22 | 0.674 | 0.588 | 4.34 |
| DFlash n_max=8 | 4.78 | 4.24 | 0.545 | 0.452 | 5.25 |
| DFlash n_max=15 | 8.49 | 3.33 | 0.607 | 0.186 | 9.95 |

## Key Findings

1. **MTP3 at 58.34 tok/s is the best consistent speed** — 89% improvement over
   the prior GGUF experiment (30.8 tok/s on UD-Q4_K_XL, old build).

2. **Q4_0 + new build is the win**: no-spec jumped from 23.7 to 26.58 tg, and
   MTP3 acceptance is excellent (0.73-0.83).

3. **DFlash n_max=5 beats MTP3 on code** (56.37 vs 53.32) with higher mean
   accepted length (4.34 vs 3.17), but loses on chat (53.22 vs 58.34).

4. **DFlash n_max >= 8 collapses** to ~4 tok/s. The batched verify forward
   with 9+ tokens hits a compute-bound cliff on current SYCL attention/GDN
   kernels. The verify forward is NOT bandwidth-bound at these batch sizes.

5. **DFlash block=16 (hipfire's 213 tok/s config) is unreachable** without
   kernel optimization. hipfire's advantage is that their batched verify
   stays bandwidth-bound even at block_size=16. Our SYCL kernels switch to
   compute-bound at much smaller batches.

## Comparison To Prior Work

| Lane | Config | tok/s | Improvement |
|------|--------|:---:|:---:|
| Prior GGUF experiment | UD-Q4_K_XL MTP3, old build | 30.8 | baseline |
| vLLM AutoRound INT4 | TP1 MTP3 | 68.0 | +121% vs prior GGUF |
| **This run** | **Q4_0 MTP3, new build** | **58.34** | **+89% vs prior GGUF** |
| hipfire (AMD R9700) | MQ4 DFlash b16 | 213 | target (not reachable yet) |

## Next Steps

1. Run the strict cold realistic suite to get headline-valid numbers.
2. Investigate the n_max=8 cliff — is it attention kernel, GDN kernel, or
   graph capture?
3. Test MTP4/MTP5 on the new build (the prior sweep was on UD-Q4_K_XL).
4. Phase 3 kernel optimization: make batched verify bandwidth-bound for
   larger n_max, which would unlock DFlash's higher acceptance.
