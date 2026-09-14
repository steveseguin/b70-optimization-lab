# Native compiler screen02 rejected on exactness

2026-09-14. Two eager control clips passed all four original-output comparisons.
The first compiled native block24 call then failed exact equality, and the
client stopped without further requests or a restart. This is a real native
compiler rejection, distinct from campaign01's earlier kernel incident before
compiler execution. The current host has no recorded new kernel/device fault.

| Request | Outcome | Preview-ready time |
| --- | --- | ---: |
| r01 eager boat | Four outputs exact; includes initial model loading | 54.7501s |
| r02 eager boat | Four outputs exact; warm control | 6.2621s |
| r03 compiled boat | First native block output differs; no completed clip | Not measured |

One warm control is not a speed-promotion sample. The target remains under one
second for each new second of video, >=256x256/24fps, nativeBF16 and original8+3
steps. The compiler candidate has no qualified speed result.

Failure receipt: block24, call1, first-stage inputs. Video output shape
`[1,64,4096]` differed in54 bytes; audio `[1,26,2048]` differed in5,923 bytes.
Both outputs were finite and shape/dtype/device matched the eager outputs.
These are **byte counts**, not element counts, error magnitudes or perceptual
quality estimates. The gate rejected them without a tolerance. The compiled
repeat, second-stage shape, remaining block calls and compiled full-clip oracle
were not reached. Compiler counters were not written because rejection preceded
the counter snapshot; no graph-count claim is made.

Identity: serverPID6502, boot`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`, packet
`prepared-encoder-compiler-03`, manifest
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
The v2 client changed campaign naming only; compiler options, source, model
receipt, control encoder, original graph and quality gates are pinned in the
preregistration/startup/request records. Source arithmetic-preservation options
included `emulate_precision_casts=True` and eager division rounding.

After failure, the endpoint queue was empty and PID6502 remained sleeping.
The current-boot kernel detector returned zero matches; no root FAULT latch
was present. The compiler gate's process-local failed state remains set.
Preserve this server and failed evidence while diagnosing; do not retry that
campaign or bypass the failed-state guard. No computer/application restart,
driver reset, power/swap/cache setting change or extra GPU request was made
in response to the numerical rejection.

The next diagnostic should identify the earliest numerical divergence. Initial
generated-source review shows native RMS normalization decomposed into Triton
reduction/reciprocal-square-root arithmetic. The original runtime warns this can
round differently. This is a concrete candidate explanation, not yet an
established cause. Preserve the original native reduction in a separately
qualified candidate rather than weakening the exact-output gate. Do not assume
that correcting one operator makes the whole block exact.
The [pinned generated-code audit](compiler-screen-02-rms-source-audit.md)
recommends a block-scoped opaque native RMS operation inserted before AOT
decomposition, with an explicit site census and unchanged argument semantics.
It also records why the existing fallback registration does not prevent this
decomposition. That successor is not implemented or qualified by this result.

Evidence: `data/compiler-screen-02/summary.json`, checksum inventory and
`evidence.json.gz`. The gzip file preserves84 original UTF-8 text files,
including request/history/prompt identities, placement and compiler receipts,
control parity reports, process/memory snapshots, failure/kernel logs, and all
generated Inductor Python sources. The exporter verified byte-preserving JSON
roundtrip and records its own hash. Full evidence/caches remain at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/compiler-screen-02` and
`encoder-server-compiler-03`; no failed patch/kernel/cache was deleted.
