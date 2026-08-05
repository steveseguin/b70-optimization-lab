# What is in the ~20.2 ms floor, and what is not

Date: 2026-08-05 America/Toronto

Status: **accounting from measurements already taken. Two components are now
excluded on step-time evidence; most of the floor remains unattributed and the
per-segment device profile is the instrument for the rest.**

## The floor

At the q12 operating point the short-context decode step is **25.82 ms**.
Removing half the all-gathers takes it to **20.21 ms**, and removing three
quarters leaves it at 20.25 ms -- so
[the collective lever saturates](2026-08-04-KEY-q12-rendezvous-halving-is-worth-22-percent.md)
and **~20.2 ms is a floor no amount of collective work can beat.**

Since 250 tok/s at the measured 3.657 tokens per step needs a **14.6 ms** step,
this floor -- not the collectives -- is what stands between the campaign and
the short-context target.

## Excluded: the drafter, at ~8% of the step

The depth sweep was originally read in tok/s and reported as **-0.6%**, which
is uninterpretable: changing depth changes acceptance, hence tokens per step,
hence tok/s, independently of speed. Re-read as step time:

| case | depth 11 | depth 7 | delta | acceptance |
| :--- | ---: | ---: | ---: | :--- |
| 8,192 | 145.27 ms | 141.33 ms | **-2.7%** | 0.031 -> 0.040 |
| 32,640 | 37.33 ms | 36.22 ms | **-3.0%** | 0.004 -> 0.009 |
| 256 sentinel | 32.97 ms | 31.92 ms | **-3.2%** | 0.251 -> 0.380 |

Removing 4 of 11 drafter passes costs a consistent ~3%, so all 11 are worth
roughly **8% of the step, about 2.6 ms**. The drafter is real but small, and
cannot be the floor. The original conclusion survives on better evidence.

## Excluded: device kernel execution, at ~2.3 ms

From the warm kineto trace, excluding the idle inter-request allreduce, total
device time is ~406 ms over ~15.3 steps. Of that, `oneccl_allgatherv_pcie` is
370 ms. **Everything else the device executes -- attention, GEMMs, elementwise,
norms, memcpy -- is ~2.3 ms per step.**

So with the gathers removed, the 20.2 ms floor contains **about 2.3 ms of
device kernel work**. Roughly 18 ms of it is *not the device computing
anything*.

## What that leaves

| component | per step | basis |
| :--- | ---: | :--- |
| device kernels, all non-collective | ~2.3 ms | kineto, warm |
| drafter (all 11 passes) | ~2.6 ms | depth sweep, step time |
| graph segment replays, 146 at 14.4 us | ~2.1 ms | 07-25 telemetry, confirmed at ~14 us by the inline arm |
| static-signature validation | ~0.36 ms | 07-25 telemetry |
| **unattributed** | **~13 ms** | -- |

The components overlap somewhat -- the drafter's own kernels are inside the
kineto figure -- so the unattributed remainder is approximate. It is
nonetheless the majority of the floor.

## The leading hypothesis, and why it is not yet a finding

Every eager break must end its cudagraph segment, which means the host waits
for the device queue to drain at that point. The 07-25 telemetry put **8.118 ms
of host time at the 48 attention boundaries** against an attention kernel that
the device runs in **~19 us**. Inlining those boundaries retired the sync
points and saved only **0.67 ms**.

The consistent reading is that host time at a boundary is mostly **absorbing
latency already in flight**, not doing work: remove the boundary and the wait
relocates rather than disappearing. That would make the floor a
queue-drain-and-refill pattern rather than any single component.

**This is a hypothesis with a bad track record in this campaign.** Five times
now a component that dominated a summed attribution turned out not to be on the
critical path. It should not be acted on until the per-segment *device* event
profile shows whether the device is busy or idle across those 20.2 ms.

## What would settle it

`VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT` records XPU event intervals for all
291 segments on the replay stream. Two outcomes, and they point opposite ways:

- **Device intervals sum to ~20 ms** -- the device is busy and the floor is
  real work that the kineto per-kernel view is missing, most likely gaps
  attributed to no kernel.
- **Device intervals sum to ~2-3 ms** -- the device is idle most of the step
  and the floor is host-side submission, which makes host-path work
  (input preparation, sampling, scheduling) the target rather than anything in
  the model.

## Boundaries

Accounting over `20260804-eventprofile-q12`, `20260804-depthwarm-d11/-d7`,
`20260804-q12-rendezvous-mod2-INEXACT-b`, `20260804-q12-rendezvous-mod4-INEXACT`
and the `20260804-warm-kernel-trace` kineto trace. Step times are derived as
`tokens_per_step / decode_tok_s_from_mean_itl`; component figures are arithmetic
on measurements, not measurements. No quantisation change, no caching or
speculation setting used to inflate any number. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
