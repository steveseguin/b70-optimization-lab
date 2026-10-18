# Packet 98 — one model load per screen bracket

CPU-only preparation, started October 18 UTC. The initial pull refused because
other work has tracked edits. A fetch confirmed local HEAD equals origin/main;
those edits were left untouched. Root had 15.6 GB free. This work has a 1 GB
build ceiling, 12 GB free-space floor, 8 GiB process limit and serial compiler
turns through packet94's helper.

V5 is a separate copy of v4. Earlier packet34 replay restrictions were read:
no arithmetic change, no synthetic/replay result as a benchmark, no retry of
failed native teardown. The existing native engine has no selection-switch
command; v5 therefore needs a native boundary command and CPU startup tests,
not merely a Python loop. Parent kernels remain frozen.

Planned milestones: native switch/reset and state-machine tests; full-shape CPU
startup/admission and seals; two-view A/A smoke and five-view A/B/A/B/A queue
proposals checked in a temporary copy. No GPU, service or model will run here.
Measured device wall-time savings are pending the coordinator's smoke; the
review14 timing figures are planning inputs, not new measurements.
