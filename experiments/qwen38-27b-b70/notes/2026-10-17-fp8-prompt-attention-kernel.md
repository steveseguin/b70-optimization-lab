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

## Variant timing (registered 2026-10-17, before the run)

Builds (`/mnt/fast-ai/builds/attn-variants-20261017/<variant>/BUILD.txt`, script
`scripts/build-attn-head256-variants.sh`): the same source and compiler as the image's library (DPC++ 2026.0.0,
6d92b1b, both B70 targets), only the head-256 prompt kernel plus one small decode kernel compiled.

- `control`: unchanged policy. Its 33 kernels have the same machine code as the image's library.
- `k64`: 64 keys per inner step (QK <256,64,32>, PV <256,32,64>); spills 192 B for FP16.
- `q128`: 128 query rows per work-group (QK/PV <128,32,32>, Out <128,256>, 16 subgroups).

The image's call also launches a paged decode kernel (`is_mix_batch=True`, the default the server uses). The
stand-alone builds lack the head-256 decode kernel and would silently fall back to PyTorch, so every arm times the
prompt kernel alone (`--mix-batch 0`, nine calls, median), in the order image, control, k64, q128, image. Each row
records any missing kernel (must be none) and a hash of the output.

- **Validity:** control equals the image within 3 % at every point, and gives the same output hash. The two image arms
  agree within 3 % (no drift). Otherwise the comparison is void.
- **Predictions:** k64 5-15 % faster at 1,280 x 100K+ (half the softmax rescale steps per key; small spill). q128 about
  the same as control at 1,280 (with two work-groups per core it has the same 94 % wave fill but reads each key tile
  for half as many rows), and faster at 832 (84 work-groups on 64 slots instead of 48 on 32).
- **Decision:** as registered above. A variant 10 % or more faster than control at 1,280 x 100K, 150K and 200K, with
  repeats equal, goes to a server build and the server checks; otherwise the kernel lever closes for tile shape.

## Result, variant timing round 1 (02:12 EDT, card 0, kernel log clean; `data/2026-10-17-attn-bench/attn-variant-*.json`)

TFLOPS per card, prompt kernel alone, median of nine calls (ratio = variant / control):

| Step x context | image | control | k64 | q128 | image again | k64 / control | q128 / control |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 832 x 100K | 49.9 | 49.9 | 56.5 | 42.7 | 49.7 | 1.132 | 0.856 |
| 832 x 200K | 49.7 | 48.5 | 55.7 | 43.2 | 49.5 | 1.148 | 0.891 |
| 1,280 x 25K | 80.0 | 79.9 | 83.8 | 52.3 | 79.2 | 1.049 | 0.655 |
| 1,280 x 100K | 71.2 | 73.6 | 78.2 | 49.3 | 72.2 | **1.063** | 0.670 |
| 1,280 x 150K | 70.4 | 71.3 | 78.1 | 48.8 | 70.5 | **1.095** | 0.684 |
| 1,280 x 200K | 69.6 | 67.7 | 77.7 | 47.4 | 70.0 | **1.148** | 0.700 |
| 2,048 x 200K | 75.1 | 75.2 | 77.7 | 48.6 | 74.3 | 1.033 | 0.646 |
| 4,096 x 200K | 74.1 | 73.7 | 76.1 | 48.1 | 73.9 | 1.033 | 0.653 |

(Full grid, 0-200K and all four steps, in the JSON files.)

- No missing kernel anywhere; every repeat bitwise equal. control and q128 give the same output hash as the image at
  every point (a query row's arithmetic does not depend on how many rows share a work-group); k64 gives a different
  one (it adds keys in a different order), still the same on every repeat.
- **Validity: missed by a hair.** The two image arms agree within 2.1 %. control is within 3 % of the image at every
  point but one: 1,280 x 100K, 3.4 % (within 3.0 % of the mean of the two image arms). control's machine code is
  identical to the image's, so this is the timing noise of nine calls, but the registered condition was 3 % at every
  point, so round 1 is void as a decision and is repeated once (below).
- q128 is out: 30-35 % slower at 1,280 and up, 10-15 % slower at 832 (faster only at an empty context). The kernel's
  rate depends on how many query rows share each key tile, more than on how full the waves are.
- k64 is faster everywhere: 13-15 % at 832, 5-15 % at 1,280 (growing with context), 2-4 % at 2,048 and 4,096. Against
  the registered bar it sits right at the line at 1,280 (two of three points under 10 % vs control; 9.1-11.3 % vs the
  mean of the image arms).

## Round 2 (registered 02:18 EDT, before the run)

Same script, card and inputs; steps 832 and 1,280 at 25K, 100K, 150K, 200K; fifteen calls per point; arms in the order
image, control, k64, control, k64, image. Round 1 is not pooled in.

- **Validity:** the two control arms and the two image arms each within 3 % of each other at every point, and control
  (mean of its two arms) within 3 % of image (mean of its two arms); otherwise void and the lever is closed as
  unmeasurable at this noise.
- **Decision (unchanged bar):** k64 (mean of its two arms) 10 % or more faster than control (mean of its two arms) at
  1,280 x 100K, 150K and 200K: build a full server library with k64 and run the server checks. Otherwise the tile-shape
  lever closes; k64's gain at 832 is then recorded as a known option, not acted on alone.

## Result, round 2 (02:19 EDT, card 0, kernel log clean; `data/2026-10-17-attn-bench/attn-variant-*-r2*.json`)

TFLOPS per card, fifteen calls per point; ratio = mean of the two k64 arms / mean of the two control arms:

| Step x context | image | control | k64 | control | k64 | image | k64 / control |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 832 x 25K | 49.4 | 49.5 | 56.6 | 49.4 | 56.8 | 49.3 | 1.147 |
| 832 x 100K | 49.9 | 49.8 | 56.3 | 49.8 | 56.1 | 49.8 | 1.129 |
| 832 x 150K | 49.7 | 49.7 | 55.9 | 49.8 | 56.1 | 49.6 | 1.126 |
| 832 x 200K | 49.4 | 49.5 | 54.9 | 49.6 | 55.4 | 49.6 | 1.113 |
| 1,280 x 25K | 78.2 | 77.4 | 80.4 | 77.5 | 81.7 | 77.7 | 1.046 |
| 1,280 x 100K | 71.3 | 71.3 | 78.3 | 71.7 | 77.9 | 72.2 | **1.092** |
| 1,280 x 150K | 70.1 | 70.3 | 73.5 | 70.0 | 77.6 | 68.9 | **1.077** |
| 1,280 x 200K | 70.2 | 68.5 | 78.2 | 70.3 | 74.9 | 68.9 | **1.103** |

- **Valid:** control pairs within 2.6 %, image pairs within 1.9 %, control vs image within 0.9 % at every point. No
  missing kernel, every repeat bitwise equal, one output hash for image and control, one for k64.
- **Decision: the tile-shape lever closes.** k64 is 7.7-10.3 % faster at 1,280 x 100K-200K, under the 10 % bar at two
  of the three points. Not built into a server.
- **Recorded as a known option:** k64 is 11-15 % faster at 832 and 8-10 % at 1,280 from 100K. On paper, prompt
  attention is about 84 s of the 152 s 200K read at 832 and about 59 s of the 118 s at 1,280, so k64 would take about
  9 s and 5 s off (6 % and 4 %). It changes the arithmetic (different output), so it needs new references, like a
  piece-size change. Fold it in only when a full kernel library is rebuilt for another reason. That build needs the
  head-256 decode kernel, whose compile takes more than 8 GiB (`BUILD.txt`).
- Why q128 lost: with half the query rows per work-group, each key tile is read for half as many rows. The rate
  follows key reuse per work-group, not wave fill. So the 832 wave waste can't be fixed by smaller query tiles. That
  leaves splitting the keys across work-groups, a kernel change, not a setting.
- Pitfall for any later kernel timing: `flash_attn_varlen_func` defaults to `is_mix_batch=True` (the server's call),
  which also launches the paged decode kernel. A library without that kernel silently times the PyTorch fallback. The
  bench now records missing kernels per row (`kernel_missing_fallback`).
