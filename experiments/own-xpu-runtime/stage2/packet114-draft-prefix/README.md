# Packet114: one smaller draft prefix, selected independently

CPU preparation only. The single candidate is **80,128** rows versus production
**91,392**, with the complete **248,320-row target head** unchanged. No GPU,
service or live queue ran. Device quality, acceptance and speed are pending.

The [preregistration](calibration/preregistration.json) was pushed in
`e2254071a` before tokenization. Its constrained objective minimizes row work
while covering at least **99.0%** of tokens in packet56's five pinned general
operations/design/publication/storage files, at their original commit. It uses
no benchmark prompts, outputs, acceptance or timing to select N. The historical
packet56 selection was read as requested. [Selection](calibration/selection.json)
was then frozen and pushed in `8d6cc3b10`: 19,285/19,477 tokens, **99.0142%**;
the previous aligned size fails. No other candidate may be tried from this bracket.

[Cost model](calibration/cost-model.json): 11,264 fewer rows remove 36.04 MB of
code/scale reads per draft call. Linear scaling of the supplied historical
0.52 ms head bucket suggests **0.0641 ms** saved per hit, with 97/19,477 corpus
tokens newly excluded. Fixed launch costs make proportional scaling optimistic;
text frequency is only a rejection proxy. Packet101 changes attention geometry,
not the head reduction. There is no fresh head-only timing for the current line.
These estimates were computed after selection and are not benchmark results.

The source is a frozen checked packet103 copy after `932df6642`, including its
packet100 DOWN layout and packet101 draft attention. Its row reduction and
argmax tie rule remain unchanged. Runtime selections are `production` and
`p114-80128`; the v5 boundary refuses every other change. Both share the existing
full target head; no second head allocation or weight upload occurs. Reset and
recapture change the draft head and argmax extents. The target's captures stay
identical. The legacy `draft-prefix.json` coverage hash still identifies the
inherited packet83 coverage metadata; **packet114 selection authority** is the
separate hash-bound calibration and bracket configuration, not that legacy field.

The KD helper [kd_reference114.py](kd_reference114.py) preserves the selected
draft prefix/geometry and projects only target storage choices for the bounded
host reference. It recomputes the draft reference against unchanged target
captures, never reuses the old full-prefix proposals. All eleven startup paths
run on CPU for both views, including KD's host and device argument paths.
No complete model inference is claimed by these payload/backend mocks.

The only coordinator entry is the proposed
[`proposed-p114-v5-B.txt`](../../ops/lane-queue/proposed-p114-v5-B.txt).
It loads one native rank pair for **A/B/A/B/A**, each view running incident64 and
**12 prompts × 128**, with every token checked against `iq3-p49-split32-v1` and
`cached_tokens=0`. Expect **9–15 minutes**, watchdog **3,600 seconds** (at least
4× the 900-second upper estimate). It requires fresh coordinator authorization,
fault review, unchanged admission and cooperative teardown. The proposal is
planned only in a temporary queue copy.

Accept the single candidate only when all outputs are exact, repeats within
each arm have identical acceptance counts, control drift is at most 3%, and
both candidate rates exceed the strongest control by at least 0.5%. Otherwise
reject. Report per-view mean acceptance and per-prompt hits/guesses, allowing
acceptance to differ between A and B. `compare.py` rechecks the decision from
receipts. This one-lifetime bracket is screening, not a fresh-server record or
promotion. It does not satisfy the full512 final gate.

Reproduce CPU preparation with `nice -n 19 taskset -c 8-15,24-31`,
`env OMP_NUM_THREADS=2`, `python3 -B`, and stdin `/dev/null`, in this order:
`restore_constants.py`, `build_engine.py`, `cpu_gate.py`, `full_shape.py`,
`reset_gate.py`, `protocol_gate.py`, `startup114.py`, `audit_sources.py`,
`limit_gate.py`, `seal_native.py`, `cpu_seal.py`, `queue_plan.py`.
Use committed selections; do not rerun the historical one-shot source copier.
Calibration verification uses `/home/steve/.venvs/vllm-xpu/bin/python3 -B
calibrate.py --verify` and reads only GGUF headers. Compilation uses packet94's
serial lock. Build logical size is below 150 MB; CPU main processes are capped
at 8 GiB. Device entry imports impose no resource limits.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md) · [retention](RETENTION.md) ·
[work note](../../../../notes/2026-10-18-own-runtime-packet114.md)
