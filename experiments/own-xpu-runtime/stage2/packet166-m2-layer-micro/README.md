# Packet166: causal two-row layer cost

This is a standalone diagnostic for one GDN layer (0) and one QSA layer (3)
of the Unsloth UD-IQ3_XXS lane, targeting `iq3-p49-split32-v1`. It does not
run a model server. Read `READY-FOR-DEVICE.json` for the final preparation state;
a proposal alone never authorizes execution.

The registered question is the cost of two causal rows with all operations in
paired submissions. Compare that with two complete sequential one-row calls.
Each arm starts from identical streams, BF16 state/history and BF16 KV. Initial
positions 2, 3 and 31 cover a four-token pool boundary and the 32-token attention
split boundary. Context capacity is 4096, attention selection budget 2048, and the
launch extent is 64 in both arms. Inputs/state are deterministic diagnostic
fixtures; weights are the real layer tensors, including the full 512-expert banks.
These are not natural prompt or full-model throughput measurements.

`micro.cpp` includes projections, HC before attention and FFN, alpha/beta and FFN
small tuples, sequential GDN recurrence across the two tokens, QSA preparation,
append/pooling, causal selection and split32 attention, routed/shared experts,
all down/mix operations, norms and both residual combinations. The paired GDN
recurrence retains the first token's BF16 state boundary. Packed-head flags are 14.
All token-local operations have paired grids or paired accumulators; there are
no two sequential M1 layer calls hidden inside the device M2 arm.

The selected bundle8 schedules are retained: p60/p73 HC, p33 large projections,
rows4 small QSA projections, p49d FFN tuple, split4 alpha/beta tuple, p82b recurrence,
p42 cooperative norms/preparation/pooling, round2 selection, p47 split32 attention,
p90 cached IQ2 gate/up, p100 tile16 down and p109 route/shared mix. Attention's
split finish includes the residual combine. Changes to pair grids and reuse
weights are local to this packet. `lineage/native-provenance.json` pins the lab source
closure; `evidence/derived-provenance.json` records the derived copies. No outside
runtime is the base of this code.

The tests compare every retained buffer between M2 and two M1 calls. Optional
proof-only stores retain first-row GDN state and convolution history and the
post-attention stream. These stores are disabled during timing. Every timed arm
is then checked, outside its timing events, against the reference buffers;
proof-only buffers are excluded from that second comparison. Error/status words
must be zero and BF16 outputs finite. GNU and Intel CPU traces must agree. Dense
CPU outputs are independently checked against the frozen arithmetic reference.
The device must also match the agreed real-weight CPU semantic-buffer hashes;
implementation scratch is compared between device arms, not against unpopulated
CPU scratch. Passing synthetic CPU data is not real-weight or device qualification.

There are 200 samples per arm, per layer and per position. Arm order alternates
AB then BA. GDN emits 22 paired or 44 serial kernel events; QSA emits 28 or56.
Only profiling timestamps enter the device-time sums. Resets, validation,
transfers, weight loading and compilation are outside these intervals. The
analyzer also retains complete device-span ratios, including gaps between events.

The primary ratio is `2 * T(M2) / (T(M1 row0) + T(M1 row1))`. The direct paired
versus two-serial ratio is also retained. Every registered layer/position must
have primary ratio ≤ 1.5 to write a stage 1 exact-prefill build brief. Otherwise the
completed measurement writes a local prefill DO-NOT-REPEAT row. Independently,
every registered context must project at least +5% one-card MTP decode to write
`MTP-VERIFY-BRIEF.md`; otherwise it writes the MTP DO-NOT-REPEAT row. If neither
qualifies, both close. Missing evidence never closes either lever.
The prefill projection is `2 * baseline / ratio`;
90 tok/s is explicitly provisional. A 36-GDN/12-QSA weighted estimate gives the
representative 48-layer verifier cost, excluding embeddings, PLE, head, transfers,
host scheduling and drafting. None is a measured full-model rate.

Beside each prefill projection, the one-card decode sensitivity transfers the
36-GDN/12-QSA weighted M2/M1 device ratio onto `1000/31.966820` ms/token:
`V2 = ratio * 1000/31.966820`, `cycle = D + V2 + (1-a)*R`, and
`tok/s = 1000*(1+a)/cycle`. [Packet147 §5](../packet147-lever-synthesis/PLAN.md#5-one-card-mtp-changed-ram-assumption-unchanged-need-for-a-new-graph),
lines 320–338, supplies `a=0.787401575`, `D=1.794747301 ms` and
`R=0.980923 ms` (approximately 0.787 and 1.79 ms). Its underlying
[packet58h evidence](../packet58h-onecard-mtp/FEASIBILITY.md#timing-model-and-sensitivity),
lines 169–216, explains their transferred, unmeasured one-card status.
Pinned copies are retained under `lineage/`.

Packet147's **57.886273 ms** limit for V2 plus new feedback/cache work belongs
to its older **29.259764 tok/s** baseline. The **31.966820** record instead needs
**≤52.814627 ms**, or **M2/M1 ≤1.688316**, to project +2% with no new costs.
The +5% verify-brief threshold is **≤1.638248**. Every reported projected rate
assumes zero new feedback/cache work; actual feedback, cache pollution/shrink,
rollback and lifetime costs must be established by the verify brief. These
are diagnostic sensitivities, not a new decode result or a full-build approval.

Preparation commands (nice 19, allowed CPU affinity, idle I/O, ≤4 GiB):

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet166-m2-layer-micro/build_engine.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet166-m2-layer-micro/run_cpu_gates.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet166-m2-layer-micro/run_cpu_gates.py --real </dev/null
```

The last command refuses while a timing process is active. Builds use the frozen
shared compiler turn and its whole-host hold. Never bypass it. `run_micro.py`
uses the existing lane reservation, fault review, drain and process supervisor;
its actual native command begins `/usr/bin/ionice -c3`. The execution gate requires
`ready_for_device:true`, three current builds, pinned sources, and the agreed
real-weight CPU oracle. First-op waits have no shorter native deadline; the
whole-process safety watchdog is 7200 seconds. No retry, device reset or server is
part of this packet. CPU preparation remains separate from device admission.

`ENTRY_PREPARE_OUTPUT` runs the actual allocation/reset and all registered arm
paths on a CPU transport, in the device-defined binary before any device API.
It substitutes zero weight backing and skips arithmetic submissions; it is not
an output gate. Actual kernel memory/resource/disk sensors are emitted for each
reset. The shared Landlock rehearsal disallows GPU access. `check_preparation.py`
checks the sensor sequence, allocation persistence, real launch environment,
actual I/O priority, declared help flags and proposal identity.

The failed shared report receipt is preserved unchanged in `evidence/rehearsal.json`
and `evidence/shared-rehearsal.*`: that attempt used packet162's matrix schema
and 0.85 threshold. `report_adapter.py` now exercises the actual
`run_micro.report_completed` entry, analyzer and every reachable decision tail on
complete synthetic layer streams derived from the native CPU buffer census.
It also replays the available real parent timestamps and rejects that different
workload as full-layer evidence. No packet166 device stream exists yet. The
private receipt and all its inputs/outputs are hash-pinned by READY and rechecked
by the execution gate; `shared_tool_limitations` records the shared limitation.
The real entry plan and `lanequeue plan` run on a temporary queue copy.
No shared tool or live queue is modified by this qualification.

To repeat the CPU-only report qualification after source edits, run
`prepare_proposal.py`, `check_preparation.py`, the seven `test_*.py` tests,
`rehearse.py`, and finally `seal_ready.py`, using the same resource limits above.
Retain the failed shared receipt. `seal_ready.py` validates existing native
source/binary identities and both real-weight CPU traces; no native source changed
in packet166b, so no rebuild or repeated model read was needed. It checks the exact
future READY closure with the real pin guard and writes READY last.

`rope.bf16.gz` retains the exact frozen BF16 rotary table in this packet. The
build restores it to `build/rope.bf16` and verifies both packed and raw hashes.
The runtime symlink remains inside this packet; it does not depend on a mutable
ancestor file. See `RETENTION.md` for the large-artifact record.
