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
completed measurement writes a local DO-NOT-REPEAT closure. Missing evidence
never closes the prefill lever. The prefill projection is `2 * baseline / ratio`;
90 tok/s is explicitly provisional. A 36-GDN/12-QSA weighted estimate gives the
representative 48-layer verifier cost, excluding embeddings, PLE, head, transfers,
host scheduling and drafting. None is a measured full-model rate.

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

The shared report adapter is presently restricted to packet162's matrix schema
and 0.85 threshold. Packet166 must retain its failed shared report receipt and
remain unready until a truthful layer-event adapter is available. The local
report tests exercise both 1.5 branches on explicitly synthetic receipts; the
separate parent test replays actual retained device timestamps and rejects that
parent workload as full-layer evidence.

`rope.bf16.gz` retains the exact frozen BF16 rotary table in this packet. The
build restores it to `build/rope.bf16` and verifies both packed and raw hashes.
The runtime symlink remains inside this packet; it does not depend on a mutable
ancestor file. See `RETENTION.md` for the large-artifact record.
