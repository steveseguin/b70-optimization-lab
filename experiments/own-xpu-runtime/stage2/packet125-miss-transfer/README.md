# Packet125: exact one-card miss transport micro

CPU preparation only. No GPU or model ran. The proposed lane-B job file is
[proposed-p125-micro-B.txt](../../ops/lane-queue/proposed-p125-micro-B.txt).
Both entries compile and plan; the coordinator chooses when to schedule them.
No live queue is changed. No engine copy or screen is authorized by a CPU pass.

Two fresh processes use physical card 2 (`0000:43:00.0`), with the existing
pre-open BDF mask, lane reservation, systemd admission, shared drain permit,
fault journal checks and cooperative stop. Expected duration is six minutes
each, watchdog thirty minutes (5×). No model load. Admission retains 8 GiB
free reserve plus an 8 GiB process budget; the native pinned arrays are below
7 GiB and the device footprint is below 1 GiB. Disk must remain above 25 GB;
build stays below 200 MB. GPU launches inherit no CPU resource caps.

All 128 captured accepted positions from packet100b are replayed through the
unchanged packet58 cache policy. Four preregistered checkpoints per prompt
include all layers: 384 cases, including 119 no-miss cases. These are **real
route IDs with simulated one-card cache masks**, never observed packet58 miss
IDs. The actual one-card receipts retain aggregate counts only. The two short
prompts and synthetic packed values make this diagnostic evidence, not a
model speed benchmark or complete packet49 quality gate.

| Path | Change |
| --- | --- |
| production | Original IQ2/IQ3 gate/up and virtual16 DOWN read pinned misses |
| tile16 | Original tile16 DOWN byte layout and exact kernel |
| bcs_serial3 | Separate gate/up/down copy calls, waiting after each |
| bcs_inflight3 | All projection copies queued before the consumer dependency |
| bcs_contiguous | One whole-expert transfer, source starts 64 bytes past a 64 KiB boundary |
| bcs_aligned | One whole-expert transfer, each source starts on a 64 KiB boundary |
| bcs_pipeline3 | Gate/up copies precede gate compute; DOWN copies can overlap gate/up and activation |

Every explicit copy uses an imported **copy-only Level Zero immediate command
list**, with its ordinal and available queue count logged. Only one copy engine
is used; multiple in-flight operations are not claimed as multiple engines.
Production already uses such an engine for later cache fills. The new proposal
measures replacing zero-copy reads with copies before expert computation.

Each case has distinct host regions. Alternatives revisit the same immutable
case bytes after a 512 MiB **device-only** cache scrub before every measurement;
there is no repeated warmed small-slab bandwidth loop and no OS cache change.
One mode order runs forward, the other backward. All cases and all modes run;
no early selection or favorable retry. The reference is an all-device run of
the unchanged production kernels. Each timed result must match gate, up,
activation, down, status and control bytes. Explicit copies additionally read
back and compare every packed miss byte after timing; destinations are poisoned
before each arm. Sources and destination slots remain owned until both queues
drain. Tile16 permutes the same packed values; it changes neither precision nor
arithmetic. Device arithmetic equality remains unmeasured until execution.

The primary rate is **sum useful missed bytes / sum wall time from route-known
to completed expert output**. It includes all ten experts' compute and no-miss
cases. Explicit-copy paths pay their 120-byte route readback and host issue/wait
costs; zero-copy does not need that readback. This is a conservative effective
miss-path rate, **not raw PCIe bandwidth** and not comparable directly to K1's
all-host device-event 14 GB/s. Per-operator device times and copy event sums are
separate diagnostics; overlapping event durations are not added as wall time.
Pointer-table setup, fixture generation, resident oracle, cache scrub and output
verification are outside timing. Future integration must still pay actual cache
policy/publication, table updates and any extra dispatch costs.

The **same** candidate must reach at least **1.5×** production in both processes,
for all cases and separately after excluding each prompt's initial checkpoint.
All exact-byte and completeness gates are independent of speed. A clean losing
micro releases its own lease and produces `engine_integration_allowed=false`.
A winner permits preparing a copied one-card engine; it does not auto-launch it.
Full chain startup/byte gates, drain check, seals and a one-load-per-arm
production/candidate/production whole-host card0 screen remain conditional.

CPU reproduction (repository root, stdin `/dev/null`):

```
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet125-miss-transfer/prepare_routes.py
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet125-miss-transfer/test_packet.py
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet125-miss-transfer/build_microbench.py
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet125-miss-transfer/queue_plan_micro.py
```

`compile_turn.py` is the exact packet94 gate. The build mirrors a hash-bound
closure of frozen production headers; `iq3_kernel.hpp` extracts the unchanged
p28 paired WG32 kernel, with no arithmetic edits. Compiler commands, source and
binary hashes, CPU checks and temporary plans are retained in `evidence/`.
Ignored binaries and compiler dumps are rebuildable and are not public assets.
[Accounting and PCIe interpretation](../../../../notes/2026-10-18-own-runtime-packet125.md).
