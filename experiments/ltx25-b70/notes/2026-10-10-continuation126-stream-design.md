# Packet 126: remove repeated CPU work from continuation streaming

Packet 126 derives from sealed packet 125, manifest
`3c2ed91975343ceb1acd2c4fe06e0fe1d7b768e0fff594865a8ec3bbbb565421`.
It is CPU prepared, not GPU qualified. The coordinator owns the live server.

The [saved-receipt analysis](2026-10-10-continuation123b-regression.md) identifies
two costs introduced or enlarged between 121 and 123b: four synchronous own-write
walks per chunk plus every status poll, and roughly 35 complete serializations
of a plan that grew 24.8%. Historical scan calls were not timed individually;
the note separates measured containing buckets, current CPU replays and causal
limits. Matched windows do not establish a further 150 ms auxiliary card-hop
penalty. The largest positive auxiliary bucket is the xpu:3 cone, partly offset
by faster sampler B; keep legacy auxiliaries for the first comparison.

## Candidate and off form

`LTX_STORAGE_SCAN_MODE=request` is the default and preserves parent paths.
`background` selects both CPU bookkeeping changes below. Neither changes model
arithmetic, tensor placement, input/output identity, client HTTP paths, snapshot
floors or GC cadence. The new mode is recorded in the launch name, server
options, all receipt types and client expectations. Incorrect/missing candidate
expectations refuse. Keep `LTX_GC_INTERVAL_SECONDS=10` initially; 60 is a separate
inherited packet-125 candidate.

1. **Accounting:** after successful qualification, one CPU helper performs the
   unchanged strict allocated-block walk. It scans periodically (0.25-second
   wait after a scan), and is notified after request completion and after the
   atomic preview JSON commit. Each notification advances a write-completion
   counter. Checks require a sample covering the observed completed writes;
   waiting is bounded at two seconds. Traversal never holds the small sample
   publication lock. Samples older than one second from **scan start**, missing
   samples, walker errors and completion timeout refuse. Every check still
   queries current filesystem free space, retaining the 50 GiB floor and frozen
   run allowance. The candidate additionally requires 256 MiB of unused run
   allowance for writes in flight. Qualification retains synchronous accounting.
   This is sampled metadata, not a filesystem quota or an atomic transaction;
   the parent also sampled concurrent writes. Near-limit operation refuses
   conservatively, with no fallback that silently changes modes.
2. **Plan integrity:** initial canonical JSON SHA256 must match the pinned inner
   plan. Every health check compares a freshly serialized typed tree against
   that verified tree using Python marshal **version 2**. No marshal bytes are
   loaded. Equal binary encodings imply equal JSON values and types. Every
   difference or unsupported binary encoding falls through to the original
   canonical SHA256 check; dictionary order/alias changes cannot bypass it.
   The original reference is never refreshed. Phase, active-request signature,
   ordering and all other authority gates still execute. Version 4 was rejected
   during CPU development because reference-count flags caused harmless alias
   changes to miss the fast path; the regression test requires 35 stable checks
   to avoid canonical serialization.

Preview MP4 and JSON fsync already execute on the separate bounded FIFO writer.
Their bytes, SHA256, exclusive rename, directory fsync, ordering, back-pressure
and failure latch are inherited unchanged. Another preview worker would not
remove a serial path present in these receipts. Anchor fsync stays intact.

## Expected result and remaining qualification

The first candidate is 145 frames, legacy auxiliaries, serial xpu:3 display,
cone, bo1/pa1, fingerprint, sampler-A display release, read-ahead0 and full
snapshots, GC10. Expected period **5.55–5.75 seconds per six seconds of new
video (0.925–0.958 s/s)**; target **5.61–5.64 seconds (0.935–0.940 s/s)**.
These are forecasts. The [final-source CPU timing record](../data/resume-20261008/continuation126-cpu-timing-sealed.json)
measures only authority work, not model throughput. Across 100 alternating
paired batches of 35 actual authority checks, the median saving is **0.143842
seconds**, with p10–p90 **0.141512–0.151660 seconds**. This excludes storage
savings. The earlier development replay is retained separately. These timings
cannot establish GPU speed, remove GC variation, or prove a card-hop duration.

The coordinator must pass the unchanged three-chain/reference/native output,
cone/display, preview hash, memory, fault and storage gates; then compare matched
fixed windows and both parities on two fresh qualified servers. Include all
cleanup/fresh-text chunks in reported mean and tails. Watch accounting sample
age, scan time, completed-write counter and authority plan-check timing in
receipts. Any remaining delay is evidence for another lever, not permission to
weaken a gate. The [contract](../recovery/20261010-continuation126-stream/CONTRACT.md)
and [launch reference](../recovery/20261010-continuation126-stream/LAUNCH.md)
provide the exact future commands. No command in that launch reference was run.

## CPU validation and seal

Sealed packet:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-126`.
Manifest SHA256:
`fe5ce9e09b7e8c86ac659c20430f85b3c83cb35bf5e8476f740610da82b60aa4`.
Inner plan SHA256:
`3858a12139fe2994281ad4ab62c8b0408a39a2020a072c84eb021b84792092e8`.
Recursive verification covered 2,128 packet files and verified the sealed125 parent.

The [build receipt](../data/resume-20261008/continuation126-build.json) records
exact discovery/client/preflight counts, source and evidence hashes, recursive
verification, and the manifest and **inner** plan identities. CPU tests cover
no request-path walk even with an injected 150 ms walker, blocked scans,
in-place growth, freshness, sticky errors, reserve/allowance refusal, completion
counters, canonical fallback and deep plan mutations, plus inherited suites.
Author and packet trees must contain zero `__pycache__` and `.pyc` files.

Work uses nice19, OMP/MKL two threads and the pinned baseline Python with `-B`.
No GPU work, model server, launch, check-only, xpu-smi, systemd operation,
port8188 access, process signal, render-device open, existing-run write,
live-client-tree write, host setting change or reboot occurs in this task.

Final CPU coverage: **696 unique recovery cases**, **2,353 client checks in 27
suites**, and **10 mocked preflight tests**. The complete recovery discovery
ran696 tests (695 passed; one inherited expected-options fixture omitted the
new `storage_scan_mode=request` field). Its corrected whole module passed32/32.
The126 client suite similarly corrected one inherited119 field-count fixture
and passed325/325 on a complete rerun; integration passed82/82. These overlapping
rechecks are not added to the unique recovery count or the27 client suites.
Original failures, provisional-pin development failures and successful rechecks
remain in the build receipt's linked logs. No sealed component changed for
these test-only corrections.
