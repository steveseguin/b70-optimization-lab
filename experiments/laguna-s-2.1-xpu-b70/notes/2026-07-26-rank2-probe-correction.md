# Laguna — CORRECTION: the rank-2 probe did not measure the benchmark workload

Date: 2026-07-26 America/Toronto

**This note supersedes the conclusions of commit `86dfb7194`**
(`2026-07-26-rank2-rescue-measured.md`). That note's "both shapes clear 102" is
withdrawn. The evidence there is retained, not deleted; only its conclusions are
void.

## Fault 1: the probe ran a different workload

The probe arm calls `LLM.generate([raw_prompt])`. The 100.524890 benchmark uses
chat completions with the model's chat template. Prompt token counts differ on
every one of the thirteen prompts:

| | prompt tokens |
| --- | --- |
| benchmark | 90, 132, 110, 102, 112, 89, 149, 111, 125, 140, 229, 112, 863 |
| probe | 49, 91, 69, 61, 72, 48, 108, 70, 85, 99, 188, 71, 823 |
| delta | +41, +41, +41, +41, +40, +41, +41, +41, +40, +41, +41, +41, +40 |

Generated-token hashes differ too. So **257/588 = 43.71% is directional
raw-prompt evidence, not a benchmark-matched result.**

## Fault 2: the projection mixed two distributions

The gain was taken from the benchmark counters and the probe, but the cost was
taken from a flat-p extrapolation:

| deepest spine node | value |
| --- | ---: |
| flat-p extrapolation `p^11` — what was used | 0.0461 |
| empirical `113/1607` — correct | **0.0703** |

Recomputed consistently on the sealed benchmark counters:

    gain = ((1607 - 1166) / 1607) x (257 / 588) = 0.1199
    loss = 113 / 1607                           = 0.0703
    net                                          = +0.0496
    emitted/cycle 3.955196 -> 4.0048  =>  **101.79 tok/s at zero overhead**

Not 102.40. **The one-alternate tree does not clear 102 even before any
implementation overhead.**

## Fault 3: the second alternate was never measured

The recorder logs top-2 for draft **position 0 only**. The 103.08 two-alternate
figure applied the position-0 rescue rate to position-1 misses, which the probe
never observed. It is unsupported.

## The decision cannot be closed by this probe

| quantity | value |
| --- | ---: |
| break-even rescue rate | 113/441 = **25.62%** |
| needed for 102 at zero overhead | **46.77%** |
| needed for 102 at 0.2% overhead | **49.70%** |
| measured (mismatched workload) | 43.71% |
| Wilson 95% interval | **39.75% – 47.74%** |

The interval does not reach the requirement. Even taken at face value this probe
is statistically incapable of authorising implementation.

## The empirical ladder: the second and third alternates are nearly worthless

Recomputing every shape on empirical counters rather than the flat-p model
changes the shape of the answer, not just its level. The marginal value of the
spine nodes an alternate displaces is far higher than the model implied:

| spine depth | empirical value |
| ---: | ---: |
| 9 | 170/1607 = 0.1058 |
| 10 | 138/1607 = 0.0859 |
| 11 | 113/1607 = 0.0703 |

Against alternate gains of 0.1199, 0.0876 and 0.0577 at the (mismatched) 43.71%:

| shape | net | emitted/cycle | projected tok/s |
| --- | ---: | ---: | ---: |
| spine 11 (measured) | — | 3.9552 | **100.52 measured** |
| spine 10 + 1 alternate | +0.0496 | 4.0048 | 101.79 |
| spine 9 + 2 alternates | +0.0513 | 4.0065 | 101.83 |
| spine 8 + 3 alternates | +0.0032 | 3.9584 | 100.61 |

**Every alternate after the first is essentially break-even**, because the spine
node it displaces is worth almost as much as the rescue it buys. The earlier
claim that two alternates were meaningfully better than one was an artifact of
the flat-p cost model understating the deep spine.

So the whole tree route reduces to a single question: is the benchmark-matched
rank-2 rescue rate at position 0 at least **46.77%**? At 43.71% it is not, and
adding alternates cannot make up the difference.

## What a valid re-measurement requires

1. A diagnostic that reuses the **exact** benchmark request construction: chat
   template, sampling parameters, EOS behaviour, prompt order, revisions, and
   environment.
2. Top-2 captured at **both** positions 0 and 1 if two alternates are to be
   evaluated.
3. An analyzer that fails closed on prompt token counts, output hashes,
   attribution row counts, four-rank equality, request boundaries, actual vLLM
   and kernel HEADs, and exactness against the q=1 teacher.
4. Per-prompt numerator and denominator, and a confidence interval.
5. Files inspected directly before any GPU launch. An edit command's success
   message is not evidence the edit landed — that already produced two wasted
   runs today.

Implementation is authorised only if a benchmark-matched conservative
projection, including measured overhead and uncertainty, clears 102 with margin.

## Standing

**100.524890 tok/s** remains the best result, and should be treated as the best
single-leg diagnostic until an independent cold confirmation and a corrected
identity record exist. Tree wiring is **not** started.
