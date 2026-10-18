# Packet58q: why production slowed, and the risk to tile16's chain

October 18, 2026; CPU-only analysis on steve-b70s. The initial pull refused
unrelated dirty orchestration files. Fetch confirmed main and origin/main at
`56287442c57cdf4d9c90ee0893e68dba2ff5648e`. Only the new packet58q directory
and this note are changed. Existing packets, evidence, queues and host state
are preserved; CURRENT.md needs no operational-state change.

Production slowed because preparing each token took about seven milliseconds
longer. It rose from 0.5835 to 7.9199 ms while the full step rose by 7.4085 ms.
Major faults rose from 0.1263 to 11.7365 per token. The final production
control shows the same pattern. Expert misses and bytes are identical across
all five saved arms, at every position. The analysis reproduces the earlier
58n numbers and aligns 2,386 positions per arm, with 1,188 in the rate window.

The likely delay is reading absent embedding/history lookup pages from the
model files. Both layouts already copy expert weights into pinned host memory;
tile16 does not uniquely avoid a file-backed expert source during decode.
Its 58n run has zero major faults, but the earlier tile16-containing port had
many. Why that page state differed is not proven. GPU and zero-copy durations
were not captured; disabled profiling zeros are not measured times.

About 79% of tile16's time saving against either 58n control is in preparation.
The layout has separate positive transfer-fixture evidence, but the full +23%
screen gain cannot be assigned to its down kernel. Production's unchanged
selection already varies by almost 16% between screens. The 58p chain cannot
count on reproducing 26.27 tok/s merely because its controls were close.

The recommendation is to keep the sealed seven-window order and whole-host
exclusion, defer optional bulk file work during the chain, and report its
actual preparation/fault counters with speed. Do not add a sequential model
pre-read: 58n explicitly forbids warming pages, and AGENTS.md forbids
host-controlled benchmark wrappers. Necessary gates may leave pages resident;
record that history without adding or reordering work to improve the cache
state. No slow tokens or windows are discarded. Independent timing and the
strict 512-token gate remain pending.

[Full numbers, evidence limits and coordinator paragraph](../experiments/own-xpu-runtime/stage2/packet58q-onecard-variance/ANALYSIS.md),
[archive-only replay validation](../experiments/own-xpu-runtime/stage2/packet58q-onecard-variance/validation.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58q-onecard-variance/CPU-ANALYSIS-CLOSEOUT.md).

The analyzer is adapted from a byte-exact copy of 58n's tool. Hash-bound gzip
snapshots preserve its small inputs and reproduce the outputs without reading
original receipts; all still-present originals are hash-checked unchanged.
Analysis runs at nice19 on cores 8–15/24–31 with python3 -B and stdin /dev/null.
No GPU, service, sudo, settings, cache drops, model payload reads, kills, live
queue edits or external submissions were performed.
