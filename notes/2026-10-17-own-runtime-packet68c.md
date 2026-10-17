# Packet68c: two rows from the production kernels

Prepared on steve-b70s, October 17, CPU only. The initial `git pull --rebase`
refused because the coordinator had unstaged live `ops/packet70-orchestration`
files. `git fetch origin main` and `git rev-list --left-right --count
HEAD...origin/main` returned `0 0`; those edits were preserved. Root started
with 18 GB free and stayed above the owner's 12 GB floor.

The [new packet](../experiments/own-xpu-runtime/stage2/packet68c-m2-from-production/README.md)
copies packet68b without editing any frozen tree. It keeps packet64's M1
reference and packet49's target arithmetic. The paired dense kernels now keep
the production compile-time tiling, split scratch and attention epilogue.
The expert kernels keep packet65 wide64's raw loads, virtualization and split
streams. Both lane quick screens pass thirteen exact requests and support that
base; this is not a claim of full-chain qualification.

The routed gate/down, GDN qkv, attention output and GDN z priorities are ready.
QSA qgate, logits and shared expert down use the same production-derived body.
Router and HC remain two serial M1 calls, explicitly labeled in the probe.
Every row keeps its own ordered FP32 sums, adjacent tree and BF16 rounding.

GNU and Intel each pass **1,428 byte checks**, including different/partial/
duplicate/invalid routes and attention stream epilogues. All four expected and
actual byte files hash to `f37663f9b84c03c190bae91b72afa05e31e9bae20ff77abc94bef510136409f6`.
The device binary builds and hashes to
`ac9979b4cfd12e3311a3dddcf5d6e3fa703f00141104daf370a1c72808d68a41`.
The build is **110,554,976 bytes**; compilation ran serially with nice19,
the requested affinity, OMP2, Python `-B`, `/dev/null` input and 8 GiB limit.
The analyzer tests and sealed lane-B plan pass. The watchdog is 3,600 seconds.

The probe adds consecutive real engine-input snapshots at 8/9, 16/17 and
32/33. It reuses its reference image to compare both outputs separately and
keeps the existing 512 MiB per-rank budget. It records actual route overlap;
the analyzer requires differing routes for every request/rank. These are
independent-state cost fixtures, not a causal two-token verifier. The original
duplicate fixtures stay separate. Packet68's measured **0.980923 ms** restore
cost is the analyzer default and is hash-bound in the seal.

No GPU, CPU model run, service, sudo, process kill, or host setting was used.
Device H(2)/H(1), ≤1.3× dense targets, both row/state checks and all thirteen
packet49 streams remain for the coordinator. The exact launch and analysis
commands are in the packet README. No projected gain is presented as measured.

The first sealed-probe commit is recorded below immediately after its push.
