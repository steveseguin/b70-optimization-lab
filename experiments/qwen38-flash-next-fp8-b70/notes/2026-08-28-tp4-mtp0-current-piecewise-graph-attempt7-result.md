# Qwen3.8 Flash-Next TP4 graph attempt 7 result

Date: 2026-08-28
Status: bounded negative during post-load graph compilation; no website or performance credit

Attempt 7 passed the schema-v3 runtime scan, reached the intended
`TORCHINDUCTOR_COMPILE_THREADS=1` treatment, loaded all 131 checkpoint shards
on all four ranks, and entered PIECEWISE graph compilation. Each rank reported
31.27 GiB of model-loading memory in 84.84-84.89 seconds. Rank 0 completed its
8.09-second Dynamo transform at 14:22:04 and logged the `(1, 64)` compile-range
cache event at 14:22:25. Graph capture did not complete and the API never
became healthy. The client, quality battery, 96+96 replay gate, and speed rows
therefore never ran.

The phase-aware resource guard latched at 14:23:27 when `MemAvailable` fell
9,025,608 KiB in one sample to 25,947,668 KiB, below the frozen 30-GiB floor.
Direct server-group TERM began at 14:23:29. The first recorded page-allocation,
TTM, and global-OOM events followed at 14:23:31, and the host killed TP3 at
14:23:32. The 12-second monotonic TERM bound escalated to KILL at 14:23:40 and
the saved process group then had no non-zombie members.

The watchdog recorded 236 samples over 256 seconds. Temporary-swap use peaked
at 6,034,112 KiB at 14:22:11 and was 6,030,436 KiB in the trip sample. The
bounded journal contains one page-allocation failure, 18 TTM buffer-eviction
failures, nine OOM invocations, and nine killed-process records. It also
contains one corrected/nonfatal root-NVMe event for `0000:01:00.0` at 14:21:47,
which the frozen event policy allowed; no B70-addressed or fatal/uncorrected
PCIe event was found.

The timing is evidence that this `compile_threads=1` arm still crossed its
preregistered host-memory floor during graph compilation. It is not proof of a
specific allocator mechanism, and it does not show whether a materially
different graph design can qualify. Because no healthy API or client work
exists, it provides no graph correctness, quality, deployment, throughput,
matrix, or website credit.

Cleanup passed: inner rc `137`, outer rc `70`, port 19684 and model workers
absent, compile/RPC paths absent, temporary swap disabled and removed, original
swap layout restored exactly, terminal and final schema-v3 runtime scans clear,
and the four cards at `42.88671875 / 42.875 / 42.875 / 42.875 MiB`.

The original 53-file ext4 evidence tree remains at
`/var/tmp/q38-piecewise-graph-a7-resource`. It was mirrored byte-for-byte,
without deleting the original, to
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt7-resource-archive`.
The archive's 53-entry `raw-manifest.sha256` has SHA-256
`b69d2b345d6b144f57e6239cb79e9ba10825c61fe53235f0eeba905bcbedf910`.
The combined resource/run/supervisor manifest has 83 entries, verifies from
the raw family root, and has SHA-256
`d28b7862fce8059a2f2eed477fc96f59d93534dadd3883869468e8232961414b`.
Its tracked copy is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt7-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt7-primary-evidence.sha256),
and the structured receipt is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt7-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt7-result.json).

This Grade-D closeout changes no family matrix, site coverage, deployment
grade, or captured eager speed. The protected family and result ledgers remain
unchanged. An identical retry is not justified; any successor needs a
materially different preregistered host-memory or graph-compilation design and
fresh evidence identity.
