# Packet124 — bundle 8 BASE with repaired drain waiting

Started at 11:16 UTC on the four-card host, within a 75-minute CPU-only box.
Pull refused unrelated dirty files. Fetch confirmed HEAD and origin/main at
`b84606017f41c5447fe925efd330bbe44a52637e`. Those files remain untouched.
Root had about 34 GB free; this preparation stops below 25 GB.

Bundle8 BASE copies packet118 bundle7 exactly: packet103 + packet109 fusion +
packet105b repaired head split + packet114's fixed 80,128-row draft prefix.
There is one composition. The native sources and runtime binaries retain their
bytes; only host waiting and packet-local preparation/orchestration change.
Every copied drain implementation clamps the sleep to zero. A deterministic
clock-crossing regression fails on the old code and passes on both fixed copies.

The prefix was selected on non-benchmark text before device timing. No retuning
from benchmark prompts, outputs, acceptance or speed is allowed. Target output
must remain `iq3-p49-split32-v1`; BF16 KV, target verification and VRAM admission
remain unchanged. New levers remain disabled slots until their declared micros
qualify and a follow-up seals exactly one additional composition.

The new readiness rule verifies original packet118 smoke/composite receipts
for the identical selection, including both lanes' >=1% gain over both controls.
It does not require packet118's chain to finish or succeed. A fresh packet124
chain may therefore replace a failed or completed bundle7 chain without the
manual other-lane pause needed by its unfixed cooldown. Existing whole-host
timing reservations remain intact. No chain, queue job, service or GPU runs here.

## CPU preparation

Four fresh GNU/Intel runs reproduce packet118's saved bundle7 output bytes.
Both real-shape ranks pass allocation admission, and all eleven chain startup
windows pass, including both KD paths. The runtime binaries are copied;
only CPU mock fixtures compile, serialized through packet94's compile turn.
The build remains below 250 MB. Resource caps are limited to CPU entry processes.

The final orchestration, launch-limit and submission checks are recorded below
when complete. Until then this is CPU preparation, not chain readiness or a
new performance result. No GPU, service, sudo, live queue, power, host memory,
swap, page-cache or reboot action is authorized or performed in this task.

## Final orchestration milestone

BASE milestone `6a613105a` was pushed immediately. The local oracle receipt
needed by the chain adapter was then copied from packet118 byte-identically;
the initial copy had excluded that nested receipt along with the active root
receipt. No oracle bytes or oracle authority changed. A local mirror's absolute
include paths are regenerated for CPU fixtures; native source and runtime
binary hashes remain identical. The retained source-bound startup gate was
rerun after final host-helper edits rather than repinning stale evidence.

All **42 policy/submission tests and four subtests pass**. They cover exact
thresholds, both lanes and the stronger control, changed-selection refusal,
source tampering, prefix preregistration, control/candidate acceptance,
complete portable submission replay, the drain race and its old-code negative
control, both recursive scans, the actual chain's fixed-drain import and the
complete readiness path with explicitly synthetic device evidence. That
synthetic test is not used in the stored readiness result.

All **six actual rank exec interceptions pass**, for smoke, composite and
chain. They preserve every inherited resource limit and unlimited address
space. An isolated CPU child rejects the old 8 GiB cap. The probe forbids
device opens and native execution and confines writes to its own scratch.
The input inventory and full eleven-window chain plan also pass.

The final control on lane A was still running during the first evidence read.
It completed while this CPU work continued. The later read verifies the actual
packet118 smoke and all six composite receipts: ratios against the stronger
control are **1.0147922893 on A** and **1.0140366894 on B**, with exact output
and repeat acceptance. These are the original bundle7 measurements, not a new
speed measurement or a gain credited to the drain repair.

`ready.json` is now **true** and `verify_ready.py` succeeds. The source decision
is `d7029dc254088641`. The fresh output is
`stage2/packet124-record-bundle/build/device-cards01-a`. A failed or finished
packet118 chain does not veto this identical selection; parent chain state
and mutable active-selection/readiness outputs are absent from its runtime
seal. Both packet124 trees pass the drain checker as a hard readiness gate.
No manual other-lane pause is required for cooldown safety. The normal
whole-host timing reservations, fault guards and VRAM gates remain unchanged.

The build is **221,749,644 bytes**, below 250 MB; root retains about **35.3 GB**
free. The startup run peaks at **1,250,124 KiB child RSS**. Native binaries were
reused byte-identically; only CPU mock fixtures compiled, serially through
packet94's compile turn. Inherited patch/header whitespace was preserved for
byte identity rather than reformatted.

[Final CPU audit](../experiments/own-xpu-runtime/ops/packet124-orchestration/cpu-final.json),
[readiness](../experiments/own-xpu-runtime/ops/packet124-orchestration/ready.json),
[coordinator runbook and disabled extension slots](../experiments/own-xpu-runtime/ops/packet124-orchestration/README.md).
Later BASE refresh needs only `orchestrate.py --evidence-only`, followed by
`verify_ready.py`; no CPU test campaign or build remains. A new runtime
dimension must earn its own source, CPU and device evidence. BASE's sealed
source closure must be preserved when preparing that separate composition.

CPU preparation finished within the 75-minute box. No GPU, service, sudo,
live queue, host setting, reboot or external submission was performed.

## Packet124b — K2 selection repair in a new copy (October 18)

The urgent CPU-only follow-up leaves packet124, packet118, the shared screen
and existing orchestration/evidence untouched. Pull refused unrelated dirty
files; fetch confirmed HEAD and origin/main both at `6ef037f4459` on entry.
Another worker subsequently advanced main to `62eaf3c3c`; its changes are retained.
Root stayed above the task's 25 GB floor. No GPU job, service, sudo, setting,
queue, marker, latch, reboot or external submission action occurred.

### Root cause and complete selection audit

`window.py` calls `p49_dispatch.pin_production_dispatch` after the K2 fixtures.
That function reads the packet's `selection.json`, removes seven names from
`selection['choices']`, maps the inherited route/recurrence aliases, and calls
`p49d_k2.measured_coverage(round3_root, dict(selection, choices=inherited))`.
Its first operation is the unchanged `selection_gate.validate_choices`.
The exact object passed by packet124 was:

```json
{"route":"route-exp32-rank4","recurrence":"rows4-shared","hc":"production","other_fusion":"fused"}
```

Packet103's twelve **configuration dimensions** produce ten target choices;
removing those seven names leaves three. Packet118/124's fifteen dimensions
produce eleven target choices, so the same exclusion leaves four. Only
`other_fusion` leaks: `target_head` is encoded in the already-excluded `head`,
and `draft_prefix` is encoded in `draft.head_prefix`. The packet118 and packet124
Python K2 implementation has the same defect. K0/K1 passed because their native
fixture command assembly never calls this Python timing postprocessor.

The new `stage2/packet124b-record-bundle/p49_dispatch.py` explicitly selects
`route`, `recurrence`, and `hc`; existing value mappings remain identical.
Missing required keys still fail. `selection_gate.py` and `p49d_k2.py` are
byte-identical, and unknown full-bundle choices still fail the full selection
identity check. No gate was relaxed and no selection or arithmetic changed.

The retained Python/native exact-key scans are in the new orchestration's
`evidence/exact-key-*-scan.txt`. Other active exact checks are intentional:
`bundle_selection.selected` and submission `validate_bundle` compare the whole
current selection; KD validates its registered full composition and unchanged
draft; suite admission checks input hash fields. The native `Selection::load`
in `p49d_submit.cpp` requires eleven choices and explicitly removes
`other_fusion` before its inherited three-key comparison. Its draft parser
already admits the registered head/prefix fields. The legacy Python
`selection_gate.verify_selection` checks the old three-field packet49d schema;
it is not a bundle-chain selection loader. No other K0–WS128 selection leak was
found. The real Python paths and native startup tests cover the active consumers.

### New gate and unchanged native identity

`ops/packet124b-orchestration/argument_gate.py` runs the actual queue commands,
window entry/parser, full selection and memory configuration, oracle/input
checks, suite/retention validation and native argument assembly for K0, K1a,
K1b, K2, W0p, KD, W2m, WS, WSs, WS128x and WS128. It captures **31 native exec
arguments**. KD reaches its real CPU reference command and both device-owner
commands; its projection and intermediate prefix/selection checks execute too.

Only operational predecessor receipts, live resource/admission/loader checks
and intermediate native results are synthetic. They stay in temporary CPU
scratch. A process audit rejects device opens, all real subprocess/native exec
and writes outside scratch. The SHA256 subprocess helper is replaced with the
same hash calculation in Python. The gate never creates device qualification.
Real operational admission is still required by the coordinator chain.

K2 additionally runs its **complete actual postprocessor**, including
`p49d_k2` timing selection, coverage, timing-event and production dispatch
validation, using four original packet124 failed-chain receipts. The unchanged
packet124 source fails with the reported strict-key error; the corrected copy
passes. `inputs/k2-replay/` retains exact gzip copies (235,940 bytes including
the manifest), original/compressed hashes and original paths. Replay restores
them only in scratch; moving the old ignored build evidence cannot break it.

Four fresh GNU/Intel CPU runs reproduce packet118's saved output bytes. Both
ranks pass real-shape memory checks; all eleven native startup paths pass.
Runtime binaries were copied from packet124, not rebuilt. The readiness policy
pins **216 native/configuration files** and both runtime binary hashes to
packet124's identity. The initial copy inventory checked **896 original
packet124 files unchanged**. Only the projection, necessary local host-path
bindings, preparation/evidence and the new CPU gate differ. The drain repair,
selection, memory plan, dispatch and strict validator retain their bytes.

Six actual smoke/composite/chain rank exec interceptions preserve every
inherited getrlimit value and unlimited address space. The isolated old finite
8 GiB cap is refused. Both recursive `scripts/check_drain_fix.py` scans pass.
CPU work uses nice19, CPUs 8–15/24–31, Python `-B`, closed stdin, with caps only
in explicit CPU entry processes. Startup peak child RSS is 1,250,184 KiB.

### Handoff

The final policy/submission suite includes nine new argument-gate tests:
**51 tests and four subtests pass**. It checks missing required keys, unchanged
strict kernel validation, unknown full-bundle rejection, all-window coverage,
the original-code failure, and mandatory argument-gate readiness, alongside
the inherited submission, prefix, lossless, drain and limit checks.

Readiness uses packet118's original smoke and matched composites for the
identical bundle7 selection, plus the explicit packet124 identity. The prefix
remains 80,128 rows, preregistered on non-benchmark text and never retuned from
benchmark prompts, output, acceptance or timing. The submission tool's complete
portable replay passes and discloses that rule. The inherited 128-token scope
continues to report `realistic_final_gate.passed=false`; strict512 is not claimed.

The fresh output is
`stage2/packet124b-record-bundle/build/device-cards01-a` (absent, not launched).
Decision: `86a78562981804e6`. Final readiness and audit receipts are linked below.
The coordinator's later refresh requires only evidence reading via
`orchestrate.py --evidence-only`, then `verify_ready.py`; CPU preparation/tests
are already complete. No manual lane pause or automatic retry is introduced.

[Ready result](../experiments/own-xpu-runtime/ops/packet124b-orchestration/ready.json),
[all-window argument gate](../experiments/own-xpu-runtime/ops/packet124b-orchestration/evidence/argument-gate.json),
[final audit](../experiments/own-xpu-runtime/ops/packet124b-orchestration/cpu-final.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet124b-record-bundle/CPU-PREPARATION-CLOSEOUT.md).

Final CPU audit and independent `verify_ready.py` both pass with `ready=true`.
Build size is **235,503,422 bytes**, below 250 MB; root has **34,272,280,576 bytes**
free at final audit. All preparation and verification completed within the
45-minute box. Native code whitespace and historical bytes were preserved.
