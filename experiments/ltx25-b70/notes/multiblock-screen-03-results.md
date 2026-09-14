# One-pass state native screen03: exact, still slower than original

September 14, 2026. All12 clips matched all four original raw outputs exactly.
Four compiled clips covered every one of the48 blocks at both native stages,
with eager/compiled and repeated compiled equality. The original BF16 model,
256x256 final size,25 frames/24fps and8+3 sampler steps are unchanged.

| Scene | Original before | Compiled | Original after |
| --- | ---: | ---: | ---: |
| Boat42 | 6.425 s | 7.378 s | 6.520 s |
| Marble17 | 6.590 s | 7.770 s | 6.404 s |
| Bird123 | 6.387 s | 8.040 s | 6.546 s |

Median compiled-minus-mean-of-adjacent-controls penalties are **1.273 seconds
preview**, **1.278 seconds raw archive readiness**, and **0.927 seconds sampler
intervals**. Every pair loses against original dispatch. There is no speed
promotion. The initial original cost123.498s, second original8.717s, and cold
all48 qualification130.138s are recorded separately from the paired samples.

Variation outside the traversal change matters: the compiled bird encoder took
2.506s versus adjacent1.809/1.896s, while compiled marble sampler intervals were
4.902s versus boat/bird4.516/4.510s. Original sampler intervals stayed3.565–3.627s.
These are approximate client event intervals, not synchronized kernel times.
The smaller isolated CPU traversal cost remains measured, but cross-process
comparisons against packet07 do not isolate its native latency contribution.
Do not label the headline worse/better solely from separate-process medians.

Native graph coverage is96 per-block stage receipts, with zero accepted warm
recompilation or fallback and unchanged default8/256 Dynamo limits. Numerical
RMS/sigmoid/tanh-GELU boundaries remain. All four raw outputs were verified before
pruning redundant tensors; lossy preview MP4s are not the quality oracle. Only
three recent campaign previews remain, with original reference tensors protected.

PID66846 remains healthy on packet08 with all48 retained, queue empty and
restored original dispatch selected. Client exit0, clean kernel postflight and
no FAULT latch. One necessary application reload from PID56711 preserved the
host boot; no reboot, driver reset or power/memory-setting changes occurred.

[Complete results](../data/multiblock-screen-03/summary.json),
[inventory](../data/multiblock-screen-03/inventory.json),
[startup and exact commands](../data/multiblock-migration-08/invocation.json).
The compressed evidence contains2,694 text files,4,080,544 bytes, SHA256
`9aa9a845ced37b3e98e7c319e83510b52a2f2cf06945f6896b8e0544c4151d8f`.
Full local evidence is under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/multiblock-screen-03`.

Next: bounded nonblocking stack sampling of the qualified retained compiled
candidate on this same application, followed by a restored control only after
all diagnostic quality/profile gates pass. This distinguishes remaining Python
validation/dispatch occupancy from compiled/native-call occupancy (which can
include waits). Profiled timing is diagnostic, not an uninstrumented speed result.
The faster-than24fps continuous-generation goal remains active and incomplete.
