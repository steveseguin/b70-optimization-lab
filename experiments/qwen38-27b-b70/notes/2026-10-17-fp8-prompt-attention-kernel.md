# How fast is the prompt-attention kernel on its own? (preregistration, 2026-10-17 00:15 EDT)

## Question

On the two-card 27B FP8 context server, a 200K prompt read in 1,280-token steps takes 118 s. The waves fit of
2026-10-16 (`2026-10-16-fp8-piece-size-prereg.md`, mechanism) puts about half of that in prompt attention, running at
about 70 TFLOPS per card, against 145-156 TFLOPS measured for a large BF16 GEMM on this card. If the kernel alone
confirms that rate, a better tile setting (the head-256 policy reads 32 keys per inner step, `fmha_utils.hpp`
`chunk_policy_head256`) could take 10-20 s off a 200K read. First measure, alone, with no server.

## Run (`scripts/bench-chunk-prefill-attn.py`, runner `scripts/run-20261017-attn-bench.sh`)

The R314 image's `vllm_xpu_kernels` `flash_attn_varlen_func`, card 0 only, Gemma stopped first and restored after:
one step of 832, 1,280, 2,048 or 4,096 query tokens (page = step, as on the exact-cache server) over a cached context
of 0, 25K, 50K, 100K, 150K, 200K tokens; 12 query heads, 2 key/value heads, head size 256, FP16 (TP2 per-card shape);
five timed calls each, median; useful work 4 x step x (context + step/2) x 256 x 12. Each pair of calls on the same
inputs must be bitwise equal.

## Predictions

- At 100K-200K context: 1,280 and 2,048 steps about 65-75 TFLOPS, 4,096 the same; 832 about 40 (two waves, half
  empty). Time per call at 1,280 x 100K about 23 ms (fit: 2.0e-6 s per wave per context token over 17 layers).
- Repeat calls bitwise equal.

## Decision rule

If the 1,280-step rate at 100K+ is under 60 % of the GEMM rate (under about 90 TFLOPS), build tile variants of the
head-256 policy (64 keys per inner step; 128 query rows per work-group) as a stand-alone kernel library, time them with
the same script, and take any variant 10 % or more faster at 1,280 x 100K+ to a server test (exactness: repeat equal
in the script, then the edit probe's 15/15 and the order probe on a server). If it is already above 60 %, the kernel
lever closes and the reading side is done for this lane.

## Result, R314 kernel (00:55 EDT, card 0, kernel log clean; `data/2026-10-17-attn-bench/attn-r314.json`)

Median of five calls, TFLOPS of useful attention work per card:

| Context | 832 step | 1,280 | 2,048 | 4,096 |
| --- | ---: | ---: | ---: | ---: |
| 25K | 39.0 | 77.5 | 77.3 | 73.9 |
| 50K | 49.7 | 76.8 | 78.5 | 75.0 |
| 100K | 49.9 | **72.2** (21.9 ms) | 76.2 | 76.0 |
| 150K | 49.6 | 69.2 | 75.0 | 74.2 |
| 200K | 49.7 | 68.4 | 74.8 | 73.8 |

- Predictions held for 1,280 (72 TFLOPS and 21.9 ms at 100K, predicted 65-75 and 23 ms) and for 2,048 / 4,096. The
  832 step does better than predicted (50, not 40): the half-empty second wave costs less than a full wave.
- Every repeat bitwise equal (24/24).
- 1,280 loses rate as the context grows (77.5 at 25K to 68.4 at 200K) where 2,048 and 4,096 hold about 75; not
  explained yet (the step is 94 % of two waves, so each wave's tail is waiting for its slowest work-group longer as
  the per-work-group work grows).
- **Decision:** 72 TFLOPS is 46-50 % of the 145-156 TFLOPS BF16 GEMM rate, under the 60 % line, so the tile variants
  are built (64 keys per inner step; 128 query rows per work-group), from the same source as the image's library
  (vllm-xpu-kernels 0.1.14.1, 6d92b1b) with a rebuilt unchanged control, and timed with the same script.
