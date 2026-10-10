# Packet 125: remove the every-other-chunk maintenance pause

The [timestamp analysis](2026-10-10-continuation-2cycle-analysis.md) changes the
diagnosis. Display, audio and preview finish in time; A preparation already runs
before display. The extra wait is after the receipt commits, before it is served.
The parent's prompt loop runs full Python collection and allocator cleanup every
ten seconds. At five to six seconds per chunk that is every second chunk, and
the same pattern is present at 121 frames. A timer replay closely predicts the
slow handoffs, including parity changes. Historical logs do not directly time
GC, so native confirmation remains required.

Packet 125 inherits sealed 124 (`897442d0…9926a5`). It changes the existing
maintenance threshold, through `LTX_GC_INTERVAL_SECONDS=10|60`, with 10 retaining
the parent path. This is smaller than adding a worker or moving device cache
cleanup into an active sampler. Both original cleanup calls stay together;
automatic GC and all byte, memory, storage and fault gates remain. The 60-second
candidate is restricted to the measured 145 frame/cone/dg0/bo1/pa1 serial display3
path with full barriers and read-ahead0. First compare legacy residency.

The candidate removes the ten-second every-other recurrence, not all maintenance.
Roughly one chunk in eleven can still pay it; fresh prompt encodes also remain.
Forecast median **5.45–5.75 seconds**, target **5.55 seconds / 0.925 s/s** for six
seconds of new video. Amortizing an observed 0.38-second slow-chunk excess over
eleven chunks suggests about 5.58 seconds /0.930 s/s, before text-mix effects.
This arithmetic is a forecast, not a measured result. Adverse range 5.75–6.10.
Do not exclude maintenance chunks from reported mean or p90.

The helper records actual GC and cache-release timestamps and keeps the latest 32
events. The next receipt and status expose them with prompt IDs, allowing the
coordinator to prove whether the historical attribution is right. Original
logs cannot separate GC time from allocator synchronization. More retained
Python cycles/allocator blocks are possible at 60; existing memory floors still
refuse pressure. Observe RSS/free/reserved memory for several full cycles,
three-chain output equality, every cone/display comparison and preview hashes.
No native performance or memory claim is closed by this CPU build.

The [contract](../recovery/20261010-continuation125-stream/CONTRACT.md),
[future launch reference](../recovery/20261010-continuation125-stream/LAUNCH.md)
and [build receipt](../data/resume-20261008/continuation125-build.json) contain
commands, identities and exact validation counts. The packet is prepared only;
all live operations remain with the coordinator. No GPU, model server, launch,
check-only, device, port8188, unit, process signal, existing-run write,
live-client-tree write or host setting change was performed.

Final CPU validation covers **655 recovery cases**, through full discovery and
full affected module/class rechecks for two corrected copied fixtures; **1,942
client checks across 25 suites** and **10 mocked preflight tests** pass. Rechecks
are not added to the unique recovery count. The earlier failed development run
is retained. All 220 numerical identities and 3,960 qualification graphs match
the parent after namespace normalization. Recursive verification covers 2,109
files; no Python bytecode caches exist in the packet or author sources.

Manifest: `3c2ed91975343ceb1acd2c4fe06e0fe1d7b768e0fff594865a8ec3bbbb565421`.
Inner plan: `238695df0c8d4bbdc0571498fd2e75aba72a4b79acb66611fa5017a641149cd2`.
The later legacy 123b snapshot also matches the timer model (49/49 classified
handoffs), but its fast-side median is 5.689 seconds. The 5.55-second forecast
is therefore a target, with native server-to-server variation still open.
