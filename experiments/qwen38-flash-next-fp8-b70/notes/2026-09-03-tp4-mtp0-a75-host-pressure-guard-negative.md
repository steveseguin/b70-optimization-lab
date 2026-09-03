# Qwen3.8 Flash-Next FP8 A75 host-pressure guard negative

Date: 2026-09-03 02:44--02:46 EDT
Status: procedural negative; the server never reached weight loading; A76 is
the byte-identical successor

A75 (the A72 deterministic graph identity served at 4352 tokens for the 4K
prefill probe) initialized its four workers and selected the Triton FP8 MoE
backend at 02:45:47. Within six seconds the supervisor's per-second host
guard wrote `FAIL A75 host-pressure or NVMe-link guard` and killed the
server: the host-pressure log shows `MemAvailable` falling from 101 GB to
41 GB while the workers pinned their 12 GiB PLE offload buffers, with the
memory PSI `full avg10` reading 5.97 then 11.41 against the guard's 10.0
cap. AER counters and NVMe reads were unchanged; no kernel event. The
launcher's health loop then saw the dead process and failed closed on the
offload receipt (`exact_11.92_log_count=0` on every rank), which is the
consequence, not the cause.

The same identity passed this guard at 2304 tokens on A70, A71 and A72. The
difference on this launch was a page cache warmed to about 34 GB just
before, so the 48 GB of pinning triggered a reclaim burst. A76
(`tools/rewrite-q38-a75-to-a76-4k-probe.py`) re-freezes the server with
fresh paths and is launched after `echo 1 > /proc/sys/vm/drop_caches`.
The memory-PSI cap is a supervisor constant inherited from the A56
lineage; if A76 trips it again, the next packet should raise it or sample
it over a longer window rather than launch behind a cold cache each time.
