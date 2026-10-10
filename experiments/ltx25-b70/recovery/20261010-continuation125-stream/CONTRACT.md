# Packet 125 CPU contract

Parent: sealed packet 124, manifest
`897442d035728c35a923840046c51c1bd43cad5097e4807c59e6d786699926a5`.
This is a prepared experiment, not a native speed or quality qualification.

The saved timelines place the alternating delay after executor exit and receipt
commit, before receipt delivery. The parent's `main.py` performs full Python
`gc.collect()` followed by `soft_empty_cache()` every ten seconds, at that exact
boundary. The same cycle exists at 121 frames. The historical evidence strongly
supports this cause but does not time the two maintenance calls separately.
A prep already precedes display; previews already have their own worker.

## Smallest lever

`LTX_GC_INTERVAL_SECONDS=10|60` defaults to **10**, the parent's exact cadence
and call order. The candidate changes only the existing periodic deadline to
60 seconds. Collection, allocator cleanup, automatic Python GC, explicit
free/unload handling, hook restoration and asset scans remain. No new worker,
queue, tensor cache, arithmetic, precision, graph, device placement or model
change is introduced. No operating-system memory or power setting changes.
The existing check happens after a prompt or a bounded idle queue wait, so the
actual maintenance interval may exceed the threshold by one prompt's duration.
It is not a hard 60-second wall deadline and never means indefinite suppression.

The 60-second form is restricted to 145 frames, two-way20-28, frame/cone,
dg0, B overlap1/A prep1, sampler-a display on xpu:3, serial completion,
read-ahead0 and full snapshot barriers. Legacy and inherited auxiliary-xpu2
residency are allowed; legacy is the first comparison. All other parent
variants remain available with 10. The candidate run name adds `-gc60`.
Invalid options fail before launch. The launch option is bound in server status,
receipts, decodes, previews and the qualification verdict, and expected by the
client. The plan pin is the canonical INNER `plan_sha256`, never the file hash.

`maintenance125.py` transforms exactly two parent source anchors in `main.py`.
Its wrapper executes the same native callbacks and propagates failures. It
records `gc_start`, `gc_done`, `cache_done`, end time, prompt ID, interval,
sequence and failure stage in a bounded 32-entry CPU ledger. Status and the
next receipt expose completed events; a receipt cannot contain housekeeping
that happens after its own commit. No callback executes under the ledger lock.
The saved evidence must bind maintenance to its prompt ID rather than assume
its containing receipt is the collected prompt.

## Exactness, memory and measurement

All 220 numerical identities and 3,960 qualification graphs remain equal to
124 after namespace/clip-ID normalization. Prefix `stream125-`, clip bases
12500000/12501000. All three qualification chains, frame145 frozen reference,
conditioned video/audio/latent bytes, every cone==display check, preview hash,
source pins, fault latches, no-eviction rules, physical-free floors and storage
guards remain. No allocator-retention benefit is counted as measured headroom.

Longer maintenance intervals can retain unreachable Python cycles and allocator
blocks longer. The native test must retain the existing every-phase memory
checks and record host RSS plus card free/reserved/allocated trends for multiple
60-second cycles. It must fail on existing floors or latches, with no fallback,
forced cleanup, retry or guard relaxation. CPU tests cannot establish a native
memory plateau. Automatic collection remains enabled and may cause other pauses.

Predict legacy median 5.45–5.75 seconds per six seconds of new video
(0.908–0.958 s/s), target 5.55 / 0.925. A roughly 0.38-second maintenance penalty
once per eleven chunks would leave about 0.035 seconds per chunk, giving about
5.58 / 0.930 on that simplified mean model. The actual fresh-text mix remains;
this is not a promise that every chunk takes 5.55 seconds. Adverse range
5.75–6.10 seconds (0.958–1.017 s/s). Compare matched text classes and retain all
maintenance chunks in mean/p90; do not remove outliers or publish forecasts.

## Preparation boundary

Use `/home/steve/.venvs/ltx25-baseline/bin/python -B`, nice19, OMP/MKL2.
The CPU runner rejects render-device opens, live sockets and signals, including
in child tests. Fakes use non-8188 loopback ports and cooperative shutdown.
Build only the new packet; recursively verify all parent hashes and preserve
changed parent sources under `provenance/packet124/`. No existing run or live
client directory is writable. Full CPU suite counts, source inventories, inner
plan pin, recursive verification and cache counts are in the build receipt.
No launch, check-only, GPU request, live endpoint, systemd operation, signal or
host change belongs to this task. Native qualification belongs to the coordinator.
