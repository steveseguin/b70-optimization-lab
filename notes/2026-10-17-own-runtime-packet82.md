# Packet82 recurrence — October 17

The CPU analysis is complete, within the 45-minute limit. The state is BF16,
and reading plus writing it costs twice the state-read number used in the
attribution table. There are already enough workgroups. The stronger lead is
the long preparation chain in one subgroup while three wait.
[Analysis and offline compiler evidence](../experiments/own-xpu-runtime/stage2/packet82-recurrence/ANALYSIS.md).

Next: two single-launch candidates that assign independent normalization and
gate work to the waiting subgroups, keeping every arithmetic chain and rounding
step. Both compiler byte gates, consecutive-token checks, full-size startup,
seals and temporary queue plans precede any coordinator screen. GPU work and
speed claims remain out of scope for this CPU preparation.

The initial pull refused other workers' dirty files; fetch showed main already
matched origin/main. Those files remain untouched. No GPU, service or host
setting changed. All work uses nice19 and cores 8–15/24–31, an 8 GiB process
ceiling for builds, one compile at a time, and less than 1 GB of build storage.

## Candidate milestone

Analysis commit `12a393fc4` was pushed before candidate edits. Three views now
build: production, rec-gates and rec-parallel. Every view passes two fresh
executions with GNU and Intel: 200 full-state comparisons per execution,
covering 320 token steps. Both in-place and separate-state bindings, both head
mappings, guards and exceptional values are covered. The CPU mirror checks raw
bytes first, then retains compact SHA256 transcripts.

GNU and Intel production differ in 20 deliberate NaN cases. Raw inspection
confirmed only NaN payload elements differ; controls and every finite/infinity
case match across compilers. Every candidate matches its own compiler's entire
production bytes, including NaN payloads. This is an existing cross-compiler
baseline difference, preserved in the evidence, not a tolerance or arithmetic
change. GPU exactness remains pending.

All six full-shape post-load startup runs pass, capture the selected recurrence
kernel, and retain actual allocation/configuration checks. The undersized-head
negative and five selection-consumer negatives refuse correctly. Both engine
builds and shared wrapper/packet Python checks pass. Candidate offline kernels
have 128 configured GRFs and no scratch spills; flag spills increase and could
hurt device speed. No speed claim follows from the CPU work. Next: seal and
check shared lane plans and temporary queue proposals.

## Sealed preparation complete

Three seals, all four lane-A plans, all six possible lane-B plans and both
temporary queue plans pass. Lane B refuses anything except the exact improving
A winner. The shared pinned wrapper and live queues are untouched. Build
storage is about 203 MiB and peak compiler memory about 709 MiB. Analysis and
candidate preparation both finished within their time boxes.

[CPU closeout](../experiments/own-xpu-runtime/stage2/packet82-recurrence/CPU-PREPARATION-CLOSEOUT.md)
and [proposed jobs](../experiments/own-xpu-runtime/stage2/packet82-recurrence/WINDOW.md)
contain the evidence and commands. The coordinator's device checks and speed
comparison are next. CPU results alone do not qualify either candidate.
