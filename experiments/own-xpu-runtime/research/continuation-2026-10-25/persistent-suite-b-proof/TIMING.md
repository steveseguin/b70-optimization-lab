# Decode-window timing observations

The twelve tuning windows total 138.793 seconds. Each starts at the second generated
token timestamp and ends at the final one. Prompt processing and the first generated
transition are excluded here; full-response throughput retains every interval.
No claim that all possible compilation effects are absent. Commands must fit wholly
inside the window for distributions and totals; occupancy instead clips boundary
commands. Native times include host dispatch and waits, not isolated GPU kernels.

| Stage | Layers | ROWs | Aborted ROWs | ROW excluding capture, ms* | Capture, s | Restore, s | Aborted ROW work, s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 13 | 7345 | 1413 | 8.147 | 10.427 | 2.482 | 14.009 |
| 1 | 12 | 7048 | 1116 | 7.542 | 4.913 | 1.016 | 9.518 |
| 2 | 12 | 6765 | 831 | 7.472 | 3.268 | 0.739 | 6.875 |
| 3 | 11 | 5941 | 0 | 8.882 | 0.000 | 0.000 | 0.000 |

*Median of the twelve per-request medians, not a pooled median. Per-request p90,
p99, minimum, maximum and counts are retained in [stage-timing.json](stage-timing.json).
Current boundaries are 0/13/25/37/48; final-stage ROW work includes the output head.
Stage0 also performs 12.410 seconds of canonical draft native work across these
windows. These observations identify costs for a boundary/ownership experiment;
they do not establish an improved cut or predict a speedup.

Capture time is included in ROW work. Aborted ROW work includes its capture and
is separate from subsequent restore; these columns must not all be added.
Stage computations overlap and likewise must not be summed into elapsed time.
The controller round-trip minus native wall includes IPC, trace writes and
scheduling. Its recorded totals by stage are 1.399/1.629/2.783/1.433 seconds; they
are not a measurement of pure coordinator CPU time. No-target-command intervals
also include pipeline dependencies and stage0 draft work, so are not GPU idle.

[Aggregate arithmetic](stage-aggregate.json), [full audit](RESULT.md).
