# Decode is a fixed ~27-34 ms per step, insensitive to every lever tried

Date: 2026-08-04 America/Toronto

Status: **measured. Two decisive negative results plus a step-time analysis that
unifies every decode observation in this campaign.**

## Two interventions that should have been large, and were not

| intervention | change in traffic or work | measured effect on 32K decode |
| :--- | :--- | ---: |
| disable expert parallelism | MoE all2all 70.8 MB/step -> 3.54 MB/step (**20x less**) | **38.829 -> 37.027 (-4.6%)** |
| draft depth 11 -> 7 | 4 of 11 sequential drafter passes removed (**36% fewer**) | **32.102 -> 31.914 (-0.6%)** |

Both arms of each pair were warm, same case order, same kernels, and passed
`retrieval_pass`. Removing 95% of the collective bytes and a third of the
drafter work each moved decode by noise.

## Step time is nearly constant

| configuration | tok/s | tokens/step | ms/step |
| :--- | ---: | ---: | ---: |
| short sentinel, 256 tokens | 131.53 | 3.66 | **27.8** |
| 32,640, q12 full stack | 39.85 | 1.08 | **27.1** |
| 32,640, qdepth depth 11 | 32.10 | 1.06 | **33.0** |
| 32,640, qdepth depth 7 | 31.91 | 1.08 | **33.8** |

**A decode step costs 27-34 ms regardless of context length (128x range), draft
depth, or expert parallelism.** Device kernel time excluding collectives is
~2.2 ms. So roughly **25-31 ms per step is fixed overhead that none of the levers
touch.**

## This unifies the campaign's observations

Everything previously explained by different mechanisms follows from one fixed
per-step cost:

- **Why speculation appears essential.** M=1 measures 0.34x not because a
  single row streams memory badly, but because one token amortises the fixed
  cost once while M=12 amortises it over 3.66 tokens at short context. The
  earlier "M=12 streams at 61% of peak, M=1 at 6%" framing described the same
  arithmetic in bandwidth terms it could not support.
- **Why acceptance is the 32K lever.** Throughput is `tokens_per_step /
  step_time`. Step time barely moves, so only tokens/step matters -- and at 32K
  the drafter delivers 1.08 against 3.66 at short context. That is exactly the
  measured 73.3% / 53.1% / 7.4% acceptance collapse.
- **Why collectives looked dominant and were not.** They occupy the step
  wall-clock but are not its cause; removing them leaves the fixed cost intact.
- **Why draft depth does not matter.** The drafter's sequential passes are also
  inside the fixed envelope, not additive to it.

## What the fixed cost is not

Excluded by measurement today: memory bandwidth (595 GB/s, 98% of spec),
compute (153 TFLOP/s per GPU), PCIe (28.7 GB/s per card), collective transport
(69% of PCIe), collective volume (20x reduction, no effect), drafter depth (36%
reduction, no effect), and GPU clocks (frequency floor at 1600 MHz worth 2%).

What remains: host-side work and synchronisation. A step issues roughly 268
kernel launches across 4 ranks with cross-rank sync points, and ~2.2 ms of that
is device compute. That is where the 25-31 ms lives, and it is the only
unexamined term left.

## Consequence for the targets

- **>150 at 32K** needs either ~76.6% acceptance (a long-context drafter) or a
  step under 7 ms (an ~4x cut in fixed overhead). Both are open; neither is a
  configuration change.
- **250 with speculation** at short context needs 6.0 tokens/step at today's
  27.8 ms, or a proportionally faster step.
- **100 without speculation** needs 10 ms/step at one token per step -- i.e.
  attacking exactly this fixed cost, since with M=1 there is nothing to amortise
  it over.

All three now reduce to the same question: **what consumes 25-31 ms per step
when only 2.2 ms is device compute?**

## The serving configuration pays this cost once per request, not once per token

Every measurement in this campaign runs `--max-num-seqs 1`: a single sequence,
one step at a time. A fixed ~25-31 ms per step is therefore charged against
1.08 tokens at 32K and 3.66 at short context, which is exactly why throughput
tracks tokens-per-step so closely.

**A deployed server batching concurrent requests amortises that same fixed cost
across every sequence in the batch.** Nothing measured here bounds aggregate
throughput under concurrency; these figures bound *single-stream* decode with a
batch of one. For "a real world deployed system", the fixed cost is the strongest
argument for serving concurrent requests, and the gap between single-stream and
batched throughput on this stack is unmeasured.

That is worth stating plainly because it cuts both ways: it does not help the
stated single-stream targets at all, and it may matter more than any of them for
actual deployment.

## What the host trace can and cannot show

Host spans from the warm trace, per step:

```
execute_context_0(0)_generation_1(12)   59.99 ms   (outer span, overlaps all)
c10d::_allgather_base_                  12.17 ms   n=98
_vllm_fa2_C::varlen_fwd                  6.59 ms   n=48
c10d::allreduce_                         1.83 ms   n=14
```

Three further spans -- `aten::copy_`, `aten::to`, `aten::_to_copy` -- report
~54 s each, one capture-boundary artifact per span, the same distortion seen in
the collective events. And `execute_context` at 59.99 ms exceeds the measured
27.9 ms step, so the outer spans overlap or include waiting.

The profiler therefore cannot attribute the fixed cost: its spans include the
waiting they are meant to explain. The allgather's 12.17 ms is the clearest
case -- removing 95% of its bytes changed decode by -4.6%, so that time is
blocking, not transferring.

**Attribution needs differential measurement, not tracing.** Two such
measurements are already done and both null (expert parallelism, draft depth).
The next candidates are `max_num_seqs`, which tests the amortisation directly,
and a host-side timer around the scheduler and sampler.

## Boundaries

Warm server, cold prefix cache, TP4, util 0.80. The qdepth arms disable the M12
shared-elementwise selector and transposed scales, which is why their absolute
figures sit below the q12 full stack; the depth-11 against depth-7 comparison is
unaffected because both arms share that configuration. Depth 7 pins
`batched=8188` so the 32,640-token prefill partition is identical across depths.
No quantisation change, no caching or speculation setting used to inflate any
number. The protected `125.4619731637751 tok/s` conventional short-decode record
is untouched.
