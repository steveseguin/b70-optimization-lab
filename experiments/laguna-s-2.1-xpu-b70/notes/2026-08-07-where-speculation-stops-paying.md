# Where speculation stops paying: the context crossover

Date: 2026-08-07 America/Toronto

Status: **measured at four contexts on both arms; the crossing itself is
interpolated, not measured.** The 8,192 point was attempted four times and lost
every time to host-side infrastructure, never to the model. What is solid is
the bracket, the mechanism, and the arithmetic that locates the crossing.

## Why this measurement exists

With the forced-eager defect fixed
([2026-08-06](2026-08-06-the-no-spec-arm-was-forced-eager-on-every-step.md)),
no-speculation decode is no longer a degraded path. It is roughly flat in
context, because 36 of 48 layers carry a 512-token window and the 12
full-attention layers read only ~400 MB per rank at 32K. Speculation, by
contrast, decays with context, because the drafter's own window is 512 against
a prompt up to 32,640.

Two curves that cross. The goal statement permits dynamic speculation, so the
crossing point is a deployment parameter, not a curiosity.

## Method

Same suite, same server settings, cold prefix cache on every row, TP4, EP4,
util 0.80. Each leg **leads with a throwaway case** so that no measured point
pays graph capture inside its own first-100-token window -- the effect that
made every historical 8,192 figure look like 7.8 tok/s on the q12 arm.

Speculative leg: `q12`, batched 8192, DFlash depth 11, width 12.
No-drafter leg: `qdepth` depth 0, `LAGUNA_NOSPEC_GRAPH=1`,
`LAGUNA_ALLOW_NO_SPEC=1`, batched 8182, M=1.

## Results

| prompt tokens | speculative (q12) | no drafter | winner |
| ---: | ---: | ---: | :--- |
| 256 (sentinel) | **162.03** | 67.52 | speculative, 2.40x |
| 1,024 | **154.82** | 65.90 | speculative, 2.35x |
| 4,096 | **78.17** | 65.83 | speculative, 1.19x |
| 8,192 | not measured | not measured | -- |
| 16,384 | not measured | not measured | -- |
| 24,576 | **unmeasurable** -- see below | | |
| 32,640 | 38.43 | **63.53** | **no drafter, 1.65x** |

The no-drafter column is flat to within 6% across a 128x range. The
speculative column halves between 1,024 and 4,096 and halves again by 32,640.

**The crossing is bracketed by measurement and located by arithmetic, not
observed directly.** At 4,096 speculation still leads by 1.19x; at 32,640 it
trails by 1.65x. Between those two points the curves cross once, because one is
flat and the other is monotonically decaying.

## Why the missing cells are missing

None of the gaps are model behaviour; all are host-side.

**24,576 is unmeasurable, and that is a finding.** Both legs that included
`laguna-lc-24576-middle` died on it and neither tripped the memory guard: one
raised `TimeoutError: RPC call to execute_model timed out` with zero device
errors, the other raised `EngineDeadError` with **195 GuC reset lines**, an
actual GPU wedge that then had to be cleared with an `xe` reload. No other
context in the suite does this. Note that 24,576 / 8,182 = 3.004, so the final
prefill chunk is about **30 tokens** -- a degenerate chunk boundary is the
obvious suspect and has not yet been checked.

**8,192 was attempted four times and lost to the host memory guard each time.**
During a run the host holds only ~35 GB available at the median, because four
workers each materialise ~17 GiB of host-side weights while the 67 GiB
checkpoint is still in page cache. Whether the guard's one-per-second sample
catches the trough is luck: legs that completed bottomed at **5.99-6.39 GB**,
legs that died bottomed at **4.14-4.65 GB**, *at the same leg shape*. The
troughs deepened over the session as the checkpoint fell out of page cache, so
each load began reading it fresh while the workers allocated.

The documented 5,242,880 KB floor was **not** lowered for any measured leg.
What was changed is `LAGUNA_MIN_SWAP_FREE_KB`: when swap free dips below it the
guard silently switches to `LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB`, which the
runbook sets a full GiB *above* the base floor, so runs that clear the
documented floor die on the stricter one anyway.

## The mechanism: speculation decays by acceptance, not by step time

Decomposing the speculative arm with `tok/s = tokens_per_step / step_time`,
from its own `spec_decode` counters:

| context | decode | tokens/step | implied step |
| ---: | ---: | ---: | ---: |
| 1,024 | 154.82 | 3.657 | 23.6 ms |
| 4,096 | 78.17 | 2.133 | 27.3 ms |
| 32,640 | 38.43 | 1.058 | 27.5 ms |

**The step time is flat at 24-27 ms across a 32x context range.** Everything
that happens to speculative throughput happens in `tokens_per_step`, which
collapses from 3.657 to 1.058 as the drafter's 512-token window loses sight of
the prompt. That is the same conclusion the 2026-08-04 note reached at 32K,
now measured as a curve rather than a point.

The no-drafter arm emits exactly one token per step at ~15 ms. So speculation
wins precisely while

    tokens_per_step  >  step_time_spec / step_time_nospec  ~=  26 / 15  ~=  1.73

which is a statement about the *drafter*, not about the machine. Interpolating
the measured tokens-per-step curve log-linearly between 4,096 and 32,640 puts
the crossing at **roughly 7,600 prompt tokens**.

That number is a property of this drafter's window. A drafter with
full-attention layers would push it out; there is no such checkpoint on disk.

## What the crossover is worth

Speculation is still the right default below the crossing, by 2.4x at the
sentinel. Above it, leaving the drafter on costs throughput outright: at 32,640
it is 38.43 against 63.53, so **switching speculation off past the crossing is
worth about 1.65x at long context** and nothing is given up at short context,
because the policy keeps speculation there.

This does not reach the 200 tok/s target at 32K. It does move the number that
had been declared unreachable, on an axis the goal statement explicitly opened
("Speculation can be dynamic if you think things run better without
speculation after a certain context").

## Boundaries

All figures q12 or qdepth depth 0 as marked, TP4, EP4, PP1, util 0.80, warm
server, **cold prefix cache on every row** (`cached_tokens_all_zero`), unique
prompts, no async scheduling. Decode figures are
`conventional_99_interval_first_100_tok_s`. Each leg's leading case is a
throwaway and is not reported. The 32,640 no-drafter figure is from
`20260806-nospec-graphfix-e` on the `-early` needle position; the sweep legs
use `-middle`. No quantisation change, and no caching or speculation setting
used to inflate any number. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched.
