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
