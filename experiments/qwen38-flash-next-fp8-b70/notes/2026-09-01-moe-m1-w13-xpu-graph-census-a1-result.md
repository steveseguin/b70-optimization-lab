# Qwen3.8 Flash-Next FP8 M1 W13 XPU-graph census A1 result

Date: 2026-09-01
Status: discovery complete; N32 exact component positive, confirmation required

The external-checkpoint, one-B70 graph census completed all 18 fresh processes
and passed its evidence manifest. Every control and candidate returned 100
unique changing-input hashes with exact eager/graph and candidate/control
agreement. Control drift was below `0.14%` in every bracket.

The sole discovery positive is the phase-specific W13
`{"BLOCK_SIZE_N":32}` configuration:

- controls: `215.274540 / 215.561060 us`;
- candidate: `166.674820 us`;
- matched latency reduction: `22.627183%`;
- control drift: `0.133007%`;
- protected W2 unchanged and all 100 outputs exact.

The remaining candidates are closed at discovery scope:

- stage 5: `-0.000784%` (neutral);
- warps 4: `-87.408864%`;
- N128: `-81.143810%`;
- K64: `-92.782520%`;
- N256: `-221.052336%`.

This is a component result, not a serving result. It does not change a
protected speed claim and does not authorize an endpoint load. The generated
confirmation packet requires 24 matched cells across layers 0/47, EP ranks
0--3, and three seeds. Every cell must be exact with at most 2% control drift;
the matched median reduction must be at least 3%, at least 20/24 cells must be
positive, and no cell may regress more than 2%. Raw timing values from
different ranks are never pooled.

The component run used the external checkpoint, but the local NVMe corrected
counter still rose from 294 to 308 while local runtime/source files were used.
The host and devices remained healthy. The confirmation runner must therefore
deduplicate shard validation, retain the external checkpoint, and stop on a
small frozen corrected-event budget rather than weakening or ignoring the
hardware signal.

Raw evidence and generated confirmation packet:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-census-a1`
