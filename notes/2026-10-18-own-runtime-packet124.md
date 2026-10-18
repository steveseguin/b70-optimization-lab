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

## Packet124c — restore oracle authority and gate the whole queue (October 18)

The reported packet124b chain passed K0, K1a, K1b, K2 and W0p, then stopped
cleanly before KD. Its queue invoked `shared_oracle.py --require-complete` in
a fresh process. Unlike the in-process orchestration adapter, that process
saw the real bundle's copied `oracle` directory and correctly refused it:
`packet49c must use the unchanged packet49 oracle authority`.
The K2 fix was not the cause. The owner's failure report records no new GPU
fault, drained teardown and no markers; this CPU task performs no recovery.

Pull refused unrelated dirty files. Fetch confirmed entry HEAD and origin/main
at `6bf515a44f200e14d24ede24a398d2c3aea024bc` on `main`. Other workers continued
advancing main; their work and all existing packet/ops trees were preserved.
This follow-up writes only the new packet124c bundle/orchestration, this note
and the cross-repository state entry. No chain, GPU, service, live queue,
sudo, setting, reboot or external submission was launched or changed.

### Copy and authority repair

The new copy preserves symlinks and excludes old chain output. Comparing every
link in packet103 and packet97 found nine dereferences: `oracle`,
`build/fusion-rope.hpp`, and seven GNU CPU fixture binaries. All nine are
restored to their exact original link targets. The eight regular files had
identical bytes. Packet97's two absent startup97e scratch links were not
copied directories/files; the audit records them as obsolete absent scratch.
Existing links remain preserved. `prepare_chain.py` no longer materializes
those seven fixture links. Native source, arithmetic and selection are unchanged.

The screen sealer correctly refused external-resolving source paths after the
repair. It remains unchanged. New `seal_view.py` makes eight local byte snapshots
for its source map (seven CPU fixtures and the suite manifest), while preserving
the actual links. The chain adapter checks original and snapshot hashes at
admission and uses the actual bundle root for `shared_oracle.P`; it no longer
redirects that check to the orchestration-local oracle alias. This preserves
both the sealer's path restriction and packet49's authority rule.

The identity audit confirms **207 native source/configuration files** equal
packet124b. Both runtime binaries retain their original hashes, also matching
packet124 and packet118. K2 projection, strict selection validator, queue
runner, fixture support, drain gate and exec-limit helper are byte-identical;
the existing error-teardown paths remain inherited. The pinned bundle7 target,
BF16 KV, unchanged verifier, full target head and non-benchmark-selected
80,128-row draft prefix are unchanged.

### Queue coverage and CPU results

The extended argument gate keeps all eleven real Python window paths, **31
intercepted native arguments**, and the complete retained K2 replay. The old
packet124 K2 implementation still fails and the corrected one passes.

It additionally runs the real `queue_runner.run` loop against the real bundle
with temporary scratch output. It executes **twelve input preflights**, **six
real pre-LATE oracle subprocesses**, actual storage and retention checks,
real prefix verification, fresh-chain/resume prerequisites and actual
`validate_success`/admission validation. It checks **55 malformed receipt or
failed-child cases**. Scheduler context, journal, elapsed gaps and generated
window receipts are explicitly synthetic; native launch is intercepted and
all synthetic evidence is deleted with scratch. Actual storage is checked
before redirecting queue writes. No synthetic device qualification is retained.

The exact `oracle_ready()` subprocess **fails on packet124b's real tree** with
the reported authority error and **passes on packet124c**, without installing
an adapter for either comparison. Symlink preservation and copied-directory
refusal tests are mandatory. The readiness verifier requires this source-bound
extended gate; an old window-only result cannot satisfy it.

All **65 policy, submission, argument and resume tests plus 11 subtests pass**.
The complete portable submission replay passes; it keeps the inherited
128-token scope and `realistic_final_gate.passed=false`, with no strict512
claim. Four fresh GNU/Intel CPU repeats match packet118's saved bytes, both
real-shape memory checks pass, all eleven native startup windows pass, and
all six actual rank exec interceptions preserve inherited limits. Both recursive
drain scans pass. CPU startup peaks at **1,249,564 KiB child RSS**.

### Handoff

`ready.json` is **true** and independent `verify_ready.py` succeeds. Decision:
`73cbd92bb2de4603`. Readiness uses packet118's original exact smoke and matched
composites, with ratios **1.0147922893 on A** and **1.0140366894 on B** against
the stronger control, plus the native identity chain. These remain the original
bundle7 measurements; no gain is credited to this repair and parent-chain
success is not required.

The fresh output is `stage2/packet124c-record-bundle/build/device-cards01-a`,
absent and unlaunched. The command is prepared in `ready.json`; the coordinator
still owns launch and normal live admission. Later refresh needs only
`orchestrate.py --evidence-only` and `verify_ready.py`. No manual lane pause,
automatic retry or relaxed gate was introduced.

Final build size: **236,694,499 bytes**, below 250 MB. Root retains
**32,806,629,376 bytes** at final audit, above the 25 GB floor. CPU verification
completed at about 12:54 UTC, within the 45-minute box. New runtime binaries
were not built; only CPU fixtures compiled. Large inherited source/provenance
files retain their bytes and restoration instructions in `RETENTION.md`.

[Readiness](../experiments/own-xpu-runtime/ops/packet124c-orchestration/ready.json),
[extended gate](../experiments/own-xpu-runtime/ops/packet124c-orchestration/evidence/argument-gate.json),
[symlink audit](../experiments/own-xpu-runtime/ops/packet124c-orchestration/inputs/symlink-audit.json),
[final CPU audit](../experiments/own-xpu-runtime/ops/packet124c-orchestration/cpu-final.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet124c-record-bundle/CPU-PREPARATION-CLOSEOUT.md).
