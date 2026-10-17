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
