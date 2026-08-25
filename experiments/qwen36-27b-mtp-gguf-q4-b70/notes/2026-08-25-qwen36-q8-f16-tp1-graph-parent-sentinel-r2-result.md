# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R2 result

State: **failed-incomplete on a redundant control log gate**. No graph
candidate ran and no matrix cell is authorized.

R2 fixed the R1 lifecycle issue. Direct/ordinary model verification passed in
34.91 seconds, GPU0 compute passed in 2.37 seconds, and the 64-token graph-off
control exited naturally in about 23 seconds after model fitting/loading. Its
stdout has no dynamic timing line. The process group cleaned normally.

At shutdown, stderr emitted the compile-guarded exact graph summary:

`device=0 requested=0 compatibility_rejected=0 device_unsupported=0
cache_entries=0 cache_limit=0 cache_hit=0 cache_miss=0 cache_full=0
direct_replay=0 recorded=0 created=0 updated=0 recreated=0 replayed=0`.

That is the complete evidence needed for the graph-off control: the summary
exists only in a graph-compiled build, binds device 0, proves cache limit zero,
and proves no graph action occurred. The retained backend does not emit the
additional human-readable `GGML_SYCL_GRAPH`, `GGML_SYCL_ENABLE_GRAPH`, and
`GGML_SYCL_GRAPH_CACHE_SIZE` lines that R2 redundantly required, so the frozen
gate stopped before the candidate.

R2 remains immutable and contributes no reusable arm. R3 may remove only those
three redundant control strings. It must keep exact summary parsing and all
zero-counter requirements for the control, while retaining every positive
candidate action marker and summary gate, lifecycle fix, identity seal,
watchdog, cleanup, and zero publication/speed authority.
