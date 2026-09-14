# Adjacent-state reuse03 native screen: exact, still slower than original

September 14, 2026. All **12/12** clips matched all four original raw outputs
byte-for-byte. Four compiled clips qualified all 48 blocks at both native
stages, including eager/compiled and repeated compiled equality. Model BF16,
256x256 final output, 25 frames/24 fps and 8+3 sampling steps are unchanged.

| Scene | Restored before | Compiled | Restored after |
| --- | ---: | ---: | ---: |
| Boat42 | 6.440 s | 7.626 s | 6.384 s |
| Marble17 | 6.406 s | 7.587 s | 6.372 s |
| Bird123 | 6.447 s | 7.649 s | 6.376 s |

Median compiled-minus-adjacent-control-mean penalties: **1.214 s preview**,
**1.215 s raw archive readiness**, and **1.167 s combined sampler intervals**.
All three scenes lost speed. This small paired screen is not a promotion.
The prior packet06 penalty was larger, but separate-process differences do not
isolate the exact speed contribution of the removed validation calls.

Cold original initialization took 69.843 seconds; second original took 8.616
seconds. Cold all48 qualification took 130.048 seconds. These costs remain
visible and are excluded from the subsequent steady paired comparisons.
Node intervals are approximate client events, not synchronized kernel timing.
Preview media remains lossy and is not the quality oracle; all four raw tensors
were independently checked before bounded retention removed redundant captures.

The runtime emitted 96 per-block graph receipts; five shared generated wrappers
are an inventory, not the qualification count. Default Dynamo limits 8/256 and
all native RMS/sigmoid/tanh-GELU boundaries remain intact. No recompilation or
fallback was accepted on warmed calls. The smaller state-scan count is exact
under the tested native workload, but does not make the compiled path faster
than restored original dispatch.

PID56711 remains healthy on packet07, idle on restored dispatch with all48
retained. Empty queue, clean kernel postflight, no FAULT latch, client exit0.
The single controlled application reload from PID39793 preserved the computer's
boot; no host reboot, driver reset or power/memory changes occurred.

[Complete request, graph and paired results](../data/multiblock-screen-02/summary.json),
[inventory](../data/multiblock-screen-02/inventory.json), and
[startup/commands](../data/multiblock-migration-07/invocation.json).
The compressed archive contains 2,688 text files and 4,001,710 bytes, SHA256
`734200912b27247d8944341f00889f151d3ce4cd4dd1664e59a4a65639b45673`.
Local source evidence remains under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/multiblock-screen-02`.

Decision: preserve the native-qualified candidate and negative timing result;
keep original dispatch selected. The [offline serializer attribution](serializer-replay-cpu-01.md)
finds only about 53 ms of potential CPU savings, insufficient to explain the
remaining penalty. Measure lifecycle/metadata traversal next without another
application reload. The real-time and continuous-generation goals remain active
and incomplete.
