# Widening the draft window does nothing, and the allocator workaround costs 5x

Date: 2026-08-04 America/Toronto

Status: **two measured results, one negative and one that invalidates earlier
work in this session. The host can no longer reproduce its own baseline.**

## Arm 1: widening the drafter's sliding window (negative)

The drafter has six layers, all `sliding_attention`, window 512, giving a
receptive field of ~3,072 tokens against a 32,640-token context. A copy with
`sliding_window: 4096` (receptive field 24,576) was served via a new
`LAGUNA_DRAFT_ROOT_OVERRIDE`, leaving the pinned original untouched.

| drafter | acceptance | conventional_99 | prefill |
| :--- | ---: | ---: | ---: |
| stock, window 512 | 0.56% | 7.632 | 3,592.9 |
| widened, window 4096 | **0.47%** | 7.648 | 3,599.6 |

**No improvement.** Acceptance is slightly worse and throughput is identical
within noise. The drafter was trained at window 512, so a wider window is
out-of-distribution; it proposes no better and costs more attention work.

The safety argument held exactly as predicted: `output_token_ids_sha256` is
**identical** across both arms and the baseline
(`154c7d6e19b3e2f5502c9dba...`). The rejection sampler assigns the emitted token
from the target's argmax unconditionally, so swapping drafters is speed-only.
That is now demonstrated rather than argued, and it makes drafter substitution a
safe thing to experiment with in future.

Widening the window is closed as a lever. Raising 32K acceptance needs a drafter
**trained** for long context, not a reconfigured one.

## Arm 2: the allocator workaround is not free (important)

`PYTORCH_ALLOC_CONF=expandable_segments:True` was introduced earlier in this
session because init otherwise fails with XPU OOM. It works, but it is
expensive:

| | prefill tok/s | decode conventional_99 |
| :--- | ---: | ---: |
| campaign baseline, 2026-08-02 | **7,345** | **39.589** |
| this session, with expandable_segments | 3,593 | 7.63 |

**Prefill halves and decode drops ~5x.** Prefill does not involve the drafter at
all, which is what isolates the cause to the allocator flag rather than to any
model-side change.

### This invalidates the kernel trace conclusions

The r11 trace was captured with **both** the torch profiler (already known to
cost 6x) and `expandable_segments`. The "collectives are 78% of device time"
finding therefore describes a doubly-degraded configuration, not the serving
system. It was already corrected down to ~19% on the basis of the unprofiled
collective benchmark; it should now be treated as **unmeasured** on a healthy
host rather than merely corrected.

What still stands, because it was measured standalone with neither the profiler
nor the allocator flag: the 45.9 us allgather latency floor, `provider: tcp`,
6.84 GB/s peak, and the nine configuration arms landing within 3%.

## The host cannot currently produce a valid measurement

Both states are broken:

- **without** `expandable_segments`: init fails, `torch.OutOfMemoryError`
  refusing 96 MiB while reporting 12.99 GiB free -- fragmentation
- **with** it: runs, but 2x slow prefill and 5x slow decode

So nothing measured on this host today is comparable to the 2026-08-02 baseline,
and no optimisation can be evaluated until that is fixed.

An idle allocation probe shows all four cards handing out 28x1 GiB chunks and
8 GiB single blocks, which is why the earlier retraction of the reboot
recommendation looked justified. That probe tested the **idle** allocator; it
does not exercise the fragmented steady state that init actually hits. The
retraction was premature.

**Recommendation: reboot the host, then re-run the stock configuration and
confirm it returns to ~7,345 prefill and ~39.589 decode before anything else is
measured.** Pair it with the GuC 70.44.1 -> 70.54.0 firmware upgrade. Both need
authorisation.

## Non-reboot recovery is exhausted

Everything short of a reboot was tried and none of it restores the host:

| attempted | result |
| :--- | :--- |
| `xe` driver unbind + module reload (six times) | init still OOMs, 96 MiB refused with ~14 GiB free |
| stock config on a *freshly reloaded* driver | same OOM -- the reload does not clear it |
| `/dev/shm` leak from ~15 killed runs | clean, 96 KiB in 4 segments; not the cause |
| host memory pressure | 79 GiB available; the failures are device-side |
| `gpu_memory_utilization` 0.80 / 0.85 / 0.90 | all fail; raising it *increases* reported free memory while the same small allocation still fails |
| `PYTORCH_ALLOC_CONF=expandable_segments:True` | initialises, but 2x slow prefill and 5x slow decode |

The `free -g` accounting shows ~44 GiB unattributed to any process, which looked
like a driver leak, but unloading the module does not reclaim it and 79 GiB
remains available -- so it is a red herring for this failure.

**A reboot is the remaining action, and it needs authorisation.** After it, the
first thing to run is the stock configuration with no allocator flag and no
profiler; it must return ~7,345 prefill and ~39.589 decode before any
optimisation is evaluated, because nothing measured in the degraded state is
comparable.

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number, output token identity verified by SHA across all three arms. The
2026-08-02 figures are quoted from that run's note and were not re-measured
today. The protected `125.4619731637751 tok/s` conventional short-decode record
is untouched.
