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

## Native and reset milestone

Both native entry builds passed, using packet82b's unchanged kernel objects.
The production shape test ran five alternating views per rank through actual
load allocation, capture, draft construction, switch and reset, with only the
backend/payload mocked. It checked 5,320 reset extents on rank0 and 5,445 on rank1,
including recurrent spare banks and draft state. The control's captured arguments
matched fresh startup after returning from the candidate. Unsupported packed
head storage refused before mutation.

The real miniature CPU backend dirtied every mutable allocation, then checked
complete byte hashes against a clean reset. Both fresh repeats on each rank
passed: 2,990 allocation comparisons, with immutable weight bytes unchanged and
attempted weight writes refused. Real rank IPC also passed two fresh five-view
brackets and matched both the parent binary and v5 fresh-process token outputs.
These miniature inputs are diagnostic fixtures, not the packet49 model suite.

The 106 inherited Python checks and ten new bracket checks pass. New coverage
includes failure in every view, stale arena identity, layout/draft refusal, cold
receipts, one load/one drain after a view failure, memory refusal before lease,
and release after a prelaunch memory race. GPU use remains untested.

Retained evidence: `experiments/own-xpu-runtime/stage2/screen/v5-bracket/evidence/`.
CPU fixture wall times are recorded there; they are not model-load savings.
Device wall-time savings remain unmeasured because this task forbids device use.
