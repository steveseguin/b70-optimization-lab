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
