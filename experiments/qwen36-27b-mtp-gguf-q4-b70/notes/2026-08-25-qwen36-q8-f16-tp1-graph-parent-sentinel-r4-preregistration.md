# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R4 preregistration

State: **preregistered, not launched**. R4 is a fresh full rerun.

R3 observed all substantive graph-on action, an exact passing summary, and
byte-identical output, but its parser stopped on three backend strings known
not to exist. R4 removes only those strings from the candidate parser. The R3
all-zero summary control gate is unchanged, and every positive candidate
action/summary/parity requirement is unchanged.

All identity, direct/ordinary model, GPU compute, lock, unsafe-variable,
single-turn, stdin, logging, timeout, process-group cleanup, postflight, and
zero publication/speed gates remain. R3 contributes no reusable arm.

Fresh root:
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r4`.
Exact acknowledgement:
`RUN qwen36-q8-f16-tp1-graph-sentinel-20260825-r4`.
