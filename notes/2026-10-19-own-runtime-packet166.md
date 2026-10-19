# Packet166: two causal rows through complete layers

The layer micro is prepared, and the real-weight CPU checks pass. It is **not
ready for a device slot**. The required shared report check accepts packet162's
matrix test and its 0.85 threshold. It rejects packet166's complete-layer events
and 1.5 threshold. That adapter is in frozen `ops/rehearse_entry.py`, so this
packet preserves the failed check and leaves `ready_for_device:false`.

No GPU work, service, sudo command, or setting change was performed. The device
executable ran only help and its sandboxed CPU preparation path. No live queue
was changed. The proposal is
[`proposed-p166-micro-B.txt`](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p166-micro-B.txt).

The new [packet](../experiments/own-xpu-runtime/stage2/packet166-m2-layer-micro/README.md)
contains one complete GDN layer and one complete QSA layer. Every device operation
has a paired submission. The reference runs two complete one-row calls. The
layer tensors come from the admitted real Unsloth checkpoint; state and inputs
are fixed diagnostic values. All state and KV remain 16-bit. Positions 2, 3 and 31
cover pooling and attention split boundaries, with capacity 4096 and launch
extent 64. This is a short-context layer diagnostic, not measured 512-token
prefill or full-model throughput.

GNU and Intel agree on all 414 retained buffer checks. M2 and two M1 calls have
identical intermediates, outputs and final state, including first-row GDN state
and convolution-history checks. The dense CPU path also agrees with the frozen
arithmetic reference. The device runner requires this agreed real-weight oracle
and checks each timed arm outside its measured event interval.

The builds are GNU host, Intel host and Intel SYCL device, with precise arithmetic
and contraction disabled. All three bind the same final native source closure.
CPU host checks peaked at 1,174,470,656 bytes. The device-defined preparation path
passed 2,412 real resets with kernel resource/disk sensors and stable allocation
identities, using CPU backing and no arithmetic submissions. The native command
uses `ionice -c3`; the actual closed launch environment and every flag were checked.

The real entry plan and lanequeue plan pass. The shared loader/help, preparation,
storage and deadline checks pass. Its report check fails only at the incompatible
packet162 report schema. The remaining identity warning is the proposal generator's
literal name, not a stale gate: the launch check obtains its identity from the
proposal. Seven local analyzer tests pass, including both 1.5 decision branches,
missing-oracle rejection and actual parent device timestamp replay. The parent
measurement remains a different workload and is correctly rejected as layer evidence.

The analyzer reports each layer and operation class, both ratio definitions,
and clearly labeled prefill/verifier projections. It requires 200 interleaved
pairs at every layer/position, all intermediate records, timed oracle checks and
the exact operation census: 22 paired events for GDN and 28 for QSA. The primary
ratio is `2*M2/(M1_row0+M1_row1)`. A complete result at or below 1.5 writes the
stage 1 prefill build brief; a result above 1.5 writes the measured local closure.
There is no device ratio yet, so neither decision has been taken. M=2 prefill
has not been closed.

The shared compiler hold was respected. During the first real-weight CPU attempt,
GNU passed but Intel's read guard stopped when our concurrent CPU preparation
probe appeared under the name `micro-device`. No GPU was involved. Running these
checks separately produced the passing GNU/Intel result. Initial packaging
failures were also fixed: historical source provenance now lives under lineage,
and the binary help probe declares its expected output explicitly.

Evidence is in the packet's `evidence/README.md`, `cpu-real-parity.json`,
`preparation.json`, `entry-plan.json`, `rehearsal.json`, `parent-device-replay.json`
and `analyzer-tests.log`. Earlier failed receipts remain retained. The 32 MiB
write plan is below three times the measured serialized fixture stream size.
The exact rotary constant is compressed and local; `RETENTION.md` records why
that 1.36 MB artifact is needed and how the build restores and verifies it.

The next required change is a truthful layer-event report adapter in the shared
rehearsal tool. After that lands, rerun the same proposal rehearsal, bind its
current hashes, and reseal readiness. The execution gate explicitly refuses a
failed shared rehearsal or stale CPU/preparation binary/proposal identities.
Until then, the proposed device row must remain unqueued.

## Packet166b — private report qualification and one-card MTP projection

The packet is now ready for a coordinator-owned device slot. Nothing was launched
or queued. This update stayed on CPU, at nice 19 on cores 8–15/24–31, with Python
bytecode disabled, stdin closed and the existing 4 GiB cap. No compiler, service,
sudo command, settings, other packet tree or shared tool was changed.

The [private report adapter](../experiments/own-xpu-runtime/stage2/packet166-m2-layer-micro/report_adapter.py)
exercises the actual report entry and analyzer. Complete synthetic layer streams
use the real native CPU buffer census and cover both briefs, MTP-only and closing
both. Invalid oracle evidence is refused before any tail is written. The retained
real parent timestamps replay correctly and are still refused as the wrong
workload. There is no packet166 device timing stream yet. Synthetic test reports
and closures are clearly separated under `evidence/private-report-cases/`; they
have not closed either real lever.

The failed shared `--report` receipt and its raw logs are unchanged. The execution
gate now requires the hash-pinned private receipt, current proposal identity and
its complete report dependencies. READY documents the shared schema limitation.
The temporary-copy lanequeue plan and real entry plan pass. The fresh CPU
preparation run passes all help flags and 2,412 real arm/reset steps. Both
unchanged native CPU traces still agree on all 414 buffers, and their source,
binary and oracle hashes remain valid. No native source changed, so no rebuild
or repeat model read was needed. The device free-space floor stays 25 GB.

The analyzer now adds a one-card MTP decode sensitivity beside every prefill
projection. [Packet147 §5, lines 320–338](../experiments/own-xpu-runtime/stage2/packet147-lever-synthesis/PLAN.md#5-one-card-mtp-changed-ram-assumption-unchanged-need-for-a-new-graph)
gives `cycle = D + V2 + (1-a)*R + new feedback/cache cost` and
`rate = 1000*(1+a)/cycle`, using `a=0.787401575`, `D=1.794747301 ms`,
`R=0.980923 ms`. These preserve the precision behind the brief's 0.787 and
1.79 ms. [Packet58h, lines 169–216](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/FEASIBILITY.md#timing-model-and-sensitivity)
explains the underlying transferred assumptions and rollback receipt. Exact
copies of both source documents are retained in packet166's `lineage/`.

Packet147's **V2 plus feedback/cache ≤57.886273 ms** was the +2% budget against
**29.259764 tok/s**, not today's record. The adapter reproduces that arithmetic.
Against **31.966820**, the corresponding budget is **52.814627 ms** and the
required M2/M1 ratio is **≤1.688316**. V2 is projected by applying the measured
36-GDN/12-QSA layer ratio to `1000/31.966820` ms. The +5% verify-brief threshold
is **≤1.638248**. These are sensitivities with zero new feedback/cache cost, not
measured one-card speed; the brief must account for those costs and memory.

Every layer/context at or below 1.5 writes the exact stage-1 prefill brief.
Independently, MTP projection at least +5% in every context writes a one-card
verify brief. Failing either condition writes that arm's negative-index row;
failing both closes both. Exact `iq3-p49-split32-v1` output, BF16 state/KV,
unchanged target verification, repeated/fresh-process checks and actual complete
performance gates remain required before any model claim.

Seven analyzer tests and the private adapter checks pass. `seal_ready.py`
rechecks the evidence and exact future marker with the real pin guard, then
writes `READY-FOR-DEVICE.json` last and checks the read-only execution gate.
The coordinator's normal device admission, fault, drain and storage guards remain
in force. No layer ratio, prefill rate or decode improvement is claimed yet.

## Device result (coordinator, 2026-10-19 08:25–08:29 UTC)

`packet166-causal-m2-layer-micro-B1` ran on lane B, card 2. Every buffer matched bytewise and matched the CPU oracle, with zero errors and 200 interleaved repeats per arm. Fault count stayed 2.

Ratio = 2·M2/(M1 row0 + M1 row1):

| Layer | Pos 2 | Pos 3 | Pos 31 |
| --- | ---: | ---: | ---: |
| GDN (layer 0) | 1.596 | 1.581 | 1.577 |
| QSA (layer 3) | 1.622 | 1.621 | 1.592 |

- Expert gate/up does not amortize: about **2.65–2.88×**. Two tokens route to different experts, and adjacent-route unions average 16.5 vs 10 experts (packet58aa).
- Expert down is about **2.03–2.08×**.
- HC norm/inject are about **1.7×**.
- Projections are about **1.24–1.33×**. Norms, activations and the combine step are about **1.0×**.

**Exact M=2 prefill stage 1: closed** by the preregistered rule (> 1.5 in every layer/context). The projected M=2 prefill would be about 111 tok/s, a 1.24× speedup; the DO-NOT-REPEAT row has been added.

**One-card MTP:** the analyzer projects **+6.46%** (34.03 tok/s, weighted ratio 1.615; the +5% limit is 1.638, the +2% limit 1.688) and wrote `MTP-VERIFY-BRIEF.md`. The projection still assumes:
- zero draft feedback/cache cost;
- transfer of the layer ratio to full wall time;
- packet58h's a = 0.787, D = 1.795 ms, R = 0.981 ms.

packet58aa's revisit condition requires a **complete** cycle, which also means pricing the expert cache shrink from 21.55 to about 18.2 GB so that the 3.34 GB draft fits in device memory (headroom is 240 bytes today). Next step: packet170, a CPU complete-cycle accounting, before any build.
