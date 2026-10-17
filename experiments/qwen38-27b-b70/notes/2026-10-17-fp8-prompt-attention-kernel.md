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
