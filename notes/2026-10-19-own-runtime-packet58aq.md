# Packet58aq — measure the one-card publication boundary and host wait

Prepared on CPU on `steve-b70s`. No device run, service, settings or live queue
changed. The 31.966820 tok/s record remains unchanged. The new packet vendors
packet58aj's full resident-lookup line and keeps `iq3-p49-split32-v1`, BF16 KV
and the complete accepted configuration.

[Packet and method](../experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/README.md)
 · [Coordinator contract](../experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/WINDOW.md)
 · [Split proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58aq-split-A.txt)
 · [Optional smoke](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58aq-smoke-A.txt).

The split is one model load, six views and all twelve prompts at 32 tokens:
control, zero-byte upload, no scatter, drain-only, wait split, control. Skipped
publications are repaired before model computation resumes. Repairs also run
in controls and are timed separately. All outputs must match the registered
oracle. The screen remains diagnostic even if all output checks pass.

The analyzer reports construction, submission, drain, repair and host-wait
scopes per token, both controls and drift. It requires matched publication
counts before attributing a saving. At least 0.67 ms/token after drift writes
an exact-change build brief; a qualifying host scope is named separately.
Otherwise a complete matched run writes a negative row. Missing new streams
or changed cadence remain inconclusive. No device values have been invented.

CPU checks include GNU/Intel complete miniature output bytes, both reset paths
with real sensors, wrong-oracle refusal, actual publication skip/repair bytes,
and a production-shape probe built with the device defines and CPU transport.
The probe preserves the real launch arguments and environment and executes
all six arms and 72 request resets. The analyzer replays all 60 real parent
device requests and refuses to draw new split conclusions from the old logs.
The inherited cold operation was 35.8815 seconds; the new 600-second wait
exceeds four times that and the 300-second minimum. Full load safety allowance
is 7200 seconds against the parent's 216.636-second load. No wall-clock
first-data proof limit is used.

The frozen shared report checker only manufactures five 128-token views. Its
smoke passes and its bracket schema failure is retained; a private adapter
supplies six 32-token fixture streams and exercises the real report code.
The shared preparation adapter requires rank arguments, so the separate
one-card device-define CPU probe is retained. These are explicit tool
limitations, not successful shared checks. The shared loader/parser, storage,
deadline and service-identity checks and real temporary lanequeue plans run
against the actual proposals. Service names derive from those proposal rows.

The split reserves 100 MB and smoke 50 MB, below three times the measured
parent writes. The build stays below 300 MB and measured CPU child RSS below
4 GiB. The packet records prior CPU probe refusal and its fix: the probe had
omitted the normal end-of-position transition; completing that transition
lets the real next reset run. This was a CPU harness fault, not a GPU fault.

Readiness is written last in the packet's `READY-FOR-DEVICE.json`, after final
source-bound gates, seal verification and proposal rehearsal. Device execution
belongs to the coordinator on whole-host lane A with PAUSE-B held. The optional
smoke is not required ahead of the split's integrated opening exact control.
