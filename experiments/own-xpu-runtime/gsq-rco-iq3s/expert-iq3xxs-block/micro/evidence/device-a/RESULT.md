# Closed micro audit

The retained native result reports all 84 pairs (168 kernels) exactly equal to the saved output **and status** bytes. Independent readback verified all source/build/fixture pins, the complete schedule, every timestamp, and the native safe teardown. The coordinator remains **failed**: its passive samples did not observe the short-lived native process holding the target device descriptor. This audit records `audit_passed: true`, `passed: false`, and `qualification_complete: false`; it does not waive that missing attestation.

There were 72 measured pairs and 12 preregistered warmup pairs. Every case/position/order combination has four measured observations; none were filtered. B/A ratios of summed GPU event durations are:

| Fixed case | Both orders | AB | BA |
| --- | ---: | ---: | ---: |
| Layer 0 | 0.422922 | 0.429558 | 0.416494 |
| Layer 22 | 0.424351 | 0.433586 | 0.415519 |
| Layer 46 | 0.415145 | 0.433110 | 0.398313 |

These are isolated event timings from this native result, not model throughput, a speed record, or a fully physically attested micro qualification. The complete means, medians, extrema and per-pair ratios are retained in [review.json](review.json); raw samples are retained without filtering.

Native teardown reports exit 0, a completed idle marker, zero in-flight work and zero live bytes. Passive post-run inventory proves the target descriptors empty; the known fault baseline and vision identity remain unchanged. No SIGTERM was attempted. The device/transfer ledgers are 963,610,200 / 965,690,280 bytes, with a 1 MiB pinned slab. The final unit's collected defaults are not treated as its live safety configuration; one active sample binds the admitted properties.

A separately admitted full Engine candidate run can qualify its **own** physical ownership and exact model results without repeating these 84 pairs. It must positively observe each admitted owner PID/start tick on its intended BDF while active, retain the same unchanged fault/vision checks, compare target output/state against the unchanged same-model authority, and prove safe closure plus physical drain. That later proof must bind the unchanged candidate arithmetic/source and describe any Engine integration delta. It cannot retroactively attest this micro's device location or change this failed terminal. Root owns that future operational decision; this audit starts no work.

The auditor read local copied sparse slices and fixtures, sources, objects, executable and closed run files only. It did not reread the model, its header, original bundles, or invoke a device/service. No full tensor digest is claimed.

The first read-only auditor invocation completed its evidence checks but failed during receipt construction because `__file__` was relative. Its source, log, raw copies and index remain under `lineage/relative-auditor-invocation/`. The same auditor was invoked with an absolute path and completed; no native execution or evidence mutation occurred.
