# Packet58v: overlap one-card expert-cache maintenance

CPU-only preparation on main. Pull refused the unrelated dirty files; fetch
confirmed HEAD and origin/main at `19d0d2b4eb26e1f0a9ea58ffd5706565a41d2b24`.
No GPU, service, live queue, host setting or frozen packet is changed.

## Measurement milestone

[Receipt analysis](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/measurement.json)
joins cache epochs to every request's prefill and generated positions. The
metric uses generated events 2–100: 1,188 positions per view. These means
are measured spans, not reciprocals of the class-balanced token rate.

| Evidence | Cache ms/token | Fills/token | Fill MB/token |
| --- | ---: | ---: | ---: |
| 58p WS | 7.061129 | 33.005051 | 65.456571 |
| 58p WS128x | 6.993898 | 33.005051 | 65.456571 |
| 58p WS128 record | 6.991363 | 33.005051 | 65.456571 |
| 58r A0/B0/A1/B1/A2 | 6.841656–7.144937 | 33.005051–33.189394 | 65.456571–65.820854 |
| 58t A0/B0/A1 | 7.153813–7.223038 | 33.005051–33.179293 | 65.456571–65.801244 |

The 58p record's token wall mean is 37.973680 ms. Every position publishes
144 pointer tables, totaling 1,179,648 bytes. Their separate publication time
was **not recorded**; it is included in cache wall and cannot be recovered
from aggregate copy counters. Fill bytes are commanded payload, not measured
PCIe traffic. Bracket repeats are diagnostics, not independent fresh-load
speed results.

The older [58i attribution](../experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/ATTRIBUTION.md)
measured 7.834869 ms cache work inside a 40.667671 ms token on 58g. The newer
record still spends 18.41% of its mean token wall in cache maintenance, far
above the 1.5 ms stop threshold. Proceed with the implementation.

Reproduce with `nice -n 19 taskset -c 8-15,24-31 python3 -B
experiments/own-xpu-runtime/stage2/packet58v-async-cache/measure.py </dev/null`.
The analyzer is capped at 4 GiB and does not import a runtime or read weights.

## Design and evidence status

Implemented in the new copy: retain tile16 arithmetic and global LRU; publish
host pointers before reusing victim slots; copy on a separate BCS event chain;
expose completed fills only at a later position boundary. Pointer publication
uses one contiguous upload plus a scatter into the existing tables. Planning
uses retained routes while the next position computes. Because those victims
cannot safely be revoked during that position, reuse begins at the following
boundary: this conservative version adds one position of lag. Pending slots
cannot be evicted again. All actual routes still update LRU recency.

Both GNU and Intel builds have passed; the final full-shape integration checks
are being refreshed. The protocol/ownership race gates and full-size K1 source
byte comparisons pass on CPU. The 87 Python policy checks pass. There is no
device correctness claim. The private packet58u policy, plus a 32 MiB metadata
allowance and 1,179,648-byte staging backing, needs 95,435,761,152 bytes of
available host RAM. The 8 GiB reserve and original device ceiling remain.

[Per-prompt sensitivities](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/projections.json)
give 28.01964 tok/s (+6.83%) if all fill DMA at an assumed 25 GB/s is hidden,
with only 0.25 ms extra cost per token. Hiding half the cache wall with 0.5 ms
overhead gives 28.49486 (+8.64%). Both assume no loss of cache hits, no bandwidth
contention and no driver serialization. They are conditional calculations,
not speed results. The impossible all-cache-removal bound is 32.07938 tok/s.

Hot-expert cache idea credit: Niko1221 / Strata. Implementation is lab-authored.
Device equality, small async smoke and performance remain pending. No gain
is measured by this preparation.
