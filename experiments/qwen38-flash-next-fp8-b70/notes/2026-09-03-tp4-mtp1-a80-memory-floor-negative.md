# Qwen3.8 Flash-Next FP8 A80 negative: the MTP1 graph server was stopped by the 16 GB host-memory floor

Date: 2026-09-03 10:17--10:27 EDT
Status: guard stop before any measurement; server itself healthy

## What happened

A80 (MTP1, `cudagraph_capture_sizes` [1, 2], KV 376,569,856 bytes, NVMe
model copy, deterministic graph identity) loaded weights in 65.9 s, resolved
`Qwen4ExpMTP`, sized the KV cache at 9,284 tokens, captured its full decode
graph (one size, since the two-token verification step is the only decode
shape with one speculative token) plus the speculator's graph, and reported
`Application startup complete` at 10:25:25. On the battery's first short
request (10:26:14-15) `MemAvailable` fell from 17.5 GB to 15,990,872 KiB,
under the supervisor's 16,000,000 KiB per-second floor, and the supervisor
stopped the server (wrapper rc 70, sentinel "host-pressure or NVMe-link
guard"); memory PSI stayed under 1.0 and AER counters at zero. The driver's
rows then failed on a dead endpoint; no output was produced.

## Reading

The MTP0 line on the same host bottomed at 20,521,148 KiB (A79), so the
MTP head and its host-side buffers cost about 4.5 GB of host memory. The
floor exists to keep the swap-less host away from the OOM killer; 12 GB
still leaves the run more headroom than any observed excursion. A81 is the
same packet with the supervisor floor at 12,000,000 KiB; the launch
pre-check (120 GB free before start), PSI, AER and bounded-read guards are
unchanged. `tools/rewrite-q38-a80-to-a81-memory-floor.py`.
