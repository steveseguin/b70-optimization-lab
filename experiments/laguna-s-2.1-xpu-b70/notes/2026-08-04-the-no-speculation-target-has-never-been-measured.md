# The no-speculation target has never been measured on the optimized stack

Date: 2026-08-04 America/Toronto

Status: **superseded 2026-08-06. The 13.31 figure was an eager-path diagnostic,
but the reason was a runtime eligibility defect, not an inherent requirement
that the optimized target use speculation. Commit `63da5e0ea` makes the M=1
target graph reachable.**

## The contract requires speculation

`_laguna_m8_shared_elementwise_contract_violations` includes:

```python
(
    speculative_config is not None
    and speculative_config.method == "dflash"
    and speculative_config.num_speculative_tokens == expected_depth,
    f"speculation is not DFlash depth {expected_depth}",
),
```

**The optimized kernels refuse to load unless DFlash speculation at depth 11 is
active.** Turning speculation off necessarily drops the model onto the generic
path, exactly as turning expert parallelism off does
([`2026-08-04-expert-parallelism-is-unmeasurable-five-contracts.md`](2026-08-04-expert-parallelism-is-unmeasurable-five-contracts.md)).

So `13.31 tok/s` is not "Laguna without speculation". It is "Laguna without
speculation **and** without the shared-elementwise kernel, the batched-exact MoE
kernel, the BF16 router top-k, and the breakable graphs" -- the campaign notes
record that this arm needed four separate gates relaxed to start at all.

## The measurements say the same thing

Every no-speculation row, across two separate runs, sits at the same value
regardless of context length or position in the suite:

| run | 1,024 (cold, 1st) | 32,640 (warm, 2nd) | 256 sentinel (warm, 3rd) |
| :--- | ---: | ---: | ---: |
| eager, no spec | 12.089 | 12.116 | 12.063 |
| graphed width-1, no spec | 12.915 | **13.308** | 12.951 |

Flat to within 2% across a 128x range of context and across cold/warm. Compare
the speculative path, which spans 8.9 cold to 163.6 warm on the same server.

A number that ignores context length and ignores warmup is not measuring
attention, KV, or memory bandwidth. It is measuring a fixed per-step cost of
roughly **75-83 ms**, on a path where none of the campaign's kernels are active.
Graph capture at width 1 moves it by 10%, which is consistent: the graphs are not
the thing that is missing.

## Why this matters for the target

The target is 100 tok/s without speculation, i.e. ~10 ms per step at one token
per step. Against 13.31 that reads as a 7.5x kernel gap, and it has been carried
that way in this campaign's notes.

That framing assumes 13.31 is what the optimized model does with speculation
removed. **It is not, and the real figure is unknown**, because the code path
that produces the campaign's throughput cannot run without speculation.

For reference, on the speculative path the warm 256-token step is ~22.4 ms at
M=12. A single-row step doing strictly less work should not cost 75-83 ms; that
gap is the generic path, not the model.

## What would actually answer it

The same kernel work the expert-parallelism finding calls for. The optimized
kernels are specialised to `(M=12, DFlash depth 11, EP4)` and each deviation
falls off to a generic implementation. Supporting `M=1` on the fast path -- or
relaxing the depth term the way `VLLM_XPU_LAGUNA_ALLOW_NO_EP` relaxes the
parallel term -- would make the no-speculation target measurable for the first
time.

Until then the honest statement is: **no-speculation decode on the optimized
stack is unmeasured, and 13.31 is a lower bound from a degraded path.**

## Consequence for "dynamic speculation"

The standing question of whether to disable speculation past some context cannot
be answered on current evidence either. Today the choice is not "speculation on
versus off"; it is "the optimized stack versus a generic one", and the optimized
stack wins by 3x at 32K for that reason as much as for any property of
speculation itself.

## Boundaries

The 12.089/12.116/12.063 and 12.915/13.308/12.951 figures are real measurements
from sealed runs; what is retracted is the interpretation placed on them, not the
numbers. No quantisation change, no caching or speculation setting used to
inflate any number. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
