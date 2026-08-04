# Measured: expert parallelism is not the lever. Removing it makes decode worse

Date: 2026-08-04 America/Toronto

Status: **measured, both arms served and passed the retrieval gate. Refutes the
central claim of
[`2026-08-04-warm-trace-decode-is-94-percent-moe-all2all.md`](2026-08-04-warm-trace-decode-is-94-percent-moe-all2all.md)
and closes the largest open hypothesis in this campaign.**

## Result

Warm 32,640-token decode, identical kernel package in both arms, only
`--no-enable-expert-parallel` differing:

| arm | decode | prefill | retrieval_pass |
| :--- | ---: | ---: | :--- |
| expert parallelism **on** | **38.829** | 6,739.6 | True |
| expert parallelism **off** | **37.027** | 6,840.3 | True |

**Removing the MoE all2all made decode 4.6% slower, not several times faster.**
Prefill improved 1.5%. The predicted 130-260 tok/s did not appear, and nothing
resembling it did.

## The control was sound

Arm A used the rebuilt grouped-GEMM and reproduced the sealed result exactly:

- output SHA `154c7d6e19b3e2f5502c9dba4cc64c16`, **bit-identical to the sealed
  reference run**
- 38.829 against 39.848 for the full stack and 39.403 with the M12 selector off
- `retrieval_pass` true on both arms

So the rebuilt binary is correct, not merely functional, and the arm-to-arm
delta is attributable to expert parallelism alone. KV cache memory also differs
between arms (4.54 vs 4.92 GiB), confirming the expert layout genuinely changed.

## Why the trace was misleading

The warm trace showed `oneccl_allgatherv_pcie` summing to **24.7 ms of a
26.4 ms step** and I read that as "~94% of the step", implying that removing the
traffic would recover almost all of it. The volume arithmetic was right --
70.8 MB per step under EP against 3.54 MB under TP, a 20x reduction, and that
reduction really happened. The **inference from it was wrong**.

Summed kernel duration is not critical-path time. Collectives on four ranks
overlap each other and overlap compute; a rank sitting inside `allgatherv` is
frequently waiting rather than transferring, and that wait is concurrent with
work elsewhere. Removing 95% of the bytes removed almost none of the wall clock,
which is only possible if the transfers were never the serialised cost.

This is the same class of error as the two earlier retractions this session --
a profiled trace read as causal, and a cold-start run compared against a warm
baseline. In each case a number that *described* the system was treated as a
number that *controlled* it. The discipline that catches it is the one that
caught it here: change the thing, measure end to end.

## What this closes

- **Do not TP-shard the experts for speed.** The kernel work is real and now
  scoped, but it buys nothing; measured, it costs ~4.6%.
- **Do not pursue collective reduction generally at 32K.** The transport already
  runs at 69% of PCIe, config tuning moves it under 3%, and eliminating 95% of
  the traffic moves decode 4.6% the wrong way.
- **The ~94% attribution should not be quoted.** The measurement stands; the
  interpretation does not.

## What remains open for decode

With collectives eliminated as a lever, the earlier acceptance finding is the
surviving explanation for the 32K target
([`2026-08-04-the-32k-target-is-blocked-by-the-drafter.md`](2026-08-04-the-32k-target-is-blocked-by-the-drafter.md)):
per-position acceptance falls 73.3% -> 53.1% -> 7.4% across 1K/4K/32K, tracking
the drafter's 512-token window, and >150 tok/s at 32K needs ~76.6%. That is a
drafter problem, unaffected by any of tonight's work.

The no-speculation target also remains unmeasured on the optimized path, since
the contract requires DFlash depth 11
([`2026-08-04-the-no-speculation-target-has-never-been-measured.md`](2026-08-04-the-no-speculation-target-has-never-been-measured.md)).

## Boundaries

Warm server, cold prefix cache, TP4, util 0.80, q12, depth 11. Both arms ran the
same case order behind an 8K warm-up, used the same composite kernel package,
and passed `retrieval_pass`. Absolute numbers are ~1-2.5% below the full stack
because the M12 shared-elementwise selector and transposed decode scales are off
in both arms; the comparison between arms is unaffected. No quantisation change,
no caching or speculation setting used to inflate any number. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
