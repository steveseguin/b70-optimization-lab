# Packet 65: routed expert occupancy and loads

CPU preparation only. No device result or 30% improvement is claimed. This is
a separate copy of packet64 sources; packet64, packet61x and queued screen
folders are unchanged. Production remains the default.

Five sealed choices share one engine. Only `choices.experts` changes:

| Choice | Gate/up + down groups | Threads/group | Change |
| --- | ---: | ---: | --- |
| `production` | 200 + 200 | 256 | Exact packet64 V8 split-stream gate/up and V16 down |
| `wg128` | 400 + 400 | 128 | Finer workgroup scheduling |
| `wg64` | 800 + 800 | 64 | Finer workgroup scheduling |
| `wide64` | 800 + 800 | 64 | Shared contiguous raw code/scale loads, same ordered sums |
| `prefetch64` | 800 + 800 | 64 | One raw `k+256` tile ahead, same sums/tree |

Screen `wide64` first. It reduces static offline load instructions without
spills. That is a mechanism observation, not a speed result. The prefetch arm
has a larger instruction body and compiler waits limit its intended overlap;
keep it as a distinct diagnostic candidate, not an assumed improvement.

[Diagnosis](OCCUPANCY.md), [coordinator commands](WINDOW.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[retention and rebuild](RETENTION.md), and
[task note](../../../../notes/2026-10-17-own-runtime-packet65.md).

The integration bar is **at least 30% less GPU time for packet57’s full
`moe_experts` class in both fresh matched pairs**, with neither rank regressing.
That includes router, route, gate/up, activation, down, mixture and FFN combine.
Gate/down alone are reported separately. Timing executes all real layers in
the full engine and fixed prompt suite. No isolated GEMV ranking is used.
A screen is diagnostic; a full packet49 quality/record chain is still needed
before integration or any public performance claim.
