# Qwen3.8 Flash-Next FP8 A53 worker-startup negative

Date: 2026-09-01
Status: bounded startup negative; no endpoint, request, quality, or speed credit

A53 crossed both prior memory-floor stopping points and loaded all 131 external
checkpoint shards on all four ranks. Weight loading took `564.41` seconds; the
four rank totals were `570.72` to `571.16` seconds at the exact retained
`31.57 GiB` per card.

Immediately after the engine selected the BLHNC KV-cache layout, rank 1 exited
inside the ordinary post-load profile path. The retained native stack reaches
PyTorch Python dispatch for an `as_strided` operation while
`determine_available_memory()` invokes `profile_run()`. Engine cancellation and
the remaining worker exits are consequences of that first rank failure.

This was not the A53 memory guard and it was not the prior host-freeze state:

- minimum `MemAvailable` was `37,684,648 KiB`, above the `16,000,000 KiB` floor;
- swap remained disabled and no swapping occurred;
- root-port corrected-event delta was zero;
- there was no OOM, B70 fault, fatal/recoverable link event, link-down report,
  or controller-down report;
- all four devices were idle after fail-closed teardown.

A51 and A52 used the same source/runtime/inference identity and both passed this
profile step; A52 also completed graph capture. A53 is therefore classified as
a one-off native startup failure, not evidence against the memory-floor change
or the graph-safe `twoshots` candidate.

One exact path-only A54 retry is allowed without reboot. It changes only
attempt, port, evidence, cache, RPC, temporary, and lifecycle identities. If
A54 repeats the same profile/dispatch failure, endpoint retries stop and the
startup phase receives report-only instrumentation before any workaround.

Raw evidence:

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt53`;
- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt53-supervisor`.
