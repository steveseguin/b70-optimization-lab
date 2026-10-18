# Packet112 CPU preparation closeout

<!-- campaign-closeout -->

Question: can exact top-16 subgroup merges halve the current route-fast
latency without changing any output? Arithmetic is `iq3-p49-split32-v1`.
The current record line, packet107 and packet110 all use the same unchanged
packet78 kernel bytes. This closes CPU preparation only, not the pending
device experiment or the model lane.

The candidate compiles for GNU, Intel host and Intel SYCL. Two fresh processes
per host compiler each pass all 2,048 cases, including 512 nonfinite rows,
with the same output identity. Both direct plans and both jobs on a temporary
lane queue pass; eleven gate tests pass. Retained build: **10,284,057 bytes**.
The proposal was pushed immediately in `f7d5ea2c3` after compilation and plans.

Useful mechanism: preserve normalization exactly, prune elements only when
sixteen better probability/index keys already exist in their own list, then
merge four levels. The candidate reduces 27 workgroup barriers to 14 and
45 compare/exchange rounds to 35 on the final subgroup's path. It keeps the
serial arithmetic and unchanged output writer, so a 50% time reduction is
uncertain. No device speed estimate is presented as a measurement.

The initial SYCL build failed on conflicting owner API headers. The local
generated hook now matches the parent's owner API override; the failed log
is retained. Rejected NaN/Inf rows have unspecified partial maximum scratch
in production itself; every output and all other scratch/guard bytes remain
checked. Packet100b contains selected IDs, not router inputs, so the retained
inputs come from packet107's CPU synthetic layer prefix. This is diagnostic
input evidence, not a realistic prompt-suite claim.

Evidence: [CPU receipt](evidence/cpu.json), [input capture](evidence/input-capture.json),
[source audit](evidence/source-audit.json), [seal](seal.json),
[plans](evidence/queue-plan.log), [tests](evidence/test-gate.log),
[work note](../../../../notes/2026-10-18-own-runtime-packet112.md).
The standalone candidate and all scripts remain in this packet; existing
packet, screen and orchestration trees were not changed by this work.

Next: the coordinator may run the two new lane-B proposals, each expected to
take 60 seconds under its 1,200-second watchdog. Both complete byte gates and
<=0.5 time ratios are mandatory. A slow or inexact process closes this arm.
Only a passing micro permits a copied packet103 integration, GNU/Intel and
startup/host-reference checks, seals, and a v5 one-load native bracket.
The p103x fix has landed in `932df6642`; the device micro remains the blocking
gate. No runtime integration or new model result is claimed.
