# Packet 59b: separate INT8 draft head

Independent packet56 candidate. It quantizes only the draft's first 91,392
head rows to signed INT8, with one FP32 scale per row. Quantization runs once
at model load, in bounded CPU chunks; proposal logits use a fixed 32-lane
FP32 reduction and BF16 output. The existing prefix argmax is unchanged.
The target's complete 248,320-row Q6 head, kernels, verification, rollback,
KV precision/capacity and state are unchanged. No packet59 code is used.

**Placement is part of this candidate.** Packet56's retained census leaves
rank1 only 89,364,320 bytes (85.22 MiB) within its unchanged 30 GiB arena.
The new codes and scales require 234,329,088 bytes (223.47 MiB), leaving a
144,964,768-byte shortfall on rank1. Instead, this packet uses the existing
rank0 draft protocol: the entire draft moves to rank0, and its only head
allocation is the INT8 prefix. Rank1 retains the original full target head.
No full head is duplicated on rank0. [Census accounting](memory-analysis.json).

| Rank | Planned device bytes | Remaining within 30 GiB |
| --- | ---: | ---: |
| 0 | 30,148,301,278 | 2,063,953,442 |
| 1 | 29,028,573,034 | 3,183,681,686 |

The [memory plan](memory-plan.json) derives from packet56's already-supported
rank0-draft, split23, 4K placement, replacing its duplicate full head with the
INT8 prefix. Its original, larger target scratch and rollback reservations
remain intact. Total allocation is 1,014,469,632 bytes above packet56's
rank1-draft census; target states and KV are never reduced. Live census and
host-memory monitors still apply. Other production placements/capacities
fail admission. Driver residency is unmeasured.

The generic screen ABI asks for draft rank1. This packet's sealed
`pipeline.Transport` explicitly maps that request to rank0 **before** memory
admission, native command creation or controller initialization. It saves
`packet59b-placement.json` with requested and effective ranks. Both native
launch receipts and census reports name the actual rank0 placement. This A/B
therefore measures INT8 **and** draft relocation, not an isolated INT8 gain.

The source inspection corrects a premise in the brief: packet56's production
head is expanded Q6, with signed-byte codes and FP32 scales per 16 columns,
plus retained source metadata, rather than BF16 weights. The kernel reads
3,200 bytes per 2,560-column row. This candidate reads 2,564, a 19.875%
reduction in unique weight bytes; physical traffic and time are unmeasured.
With the supplied 521 us head time, simple bandwidth scaling suggests about
104 us saved in that kernel, before relocation and acceptance effects. This
is a planning estimate only. Draft proposals may differ; only unchanged
target-verified tokens may be emitted.

## CPU preparation and coordinator handoff

Use only these entry points. Other inherited helpers are frozen implementation
history, not a new full-chain qualification or a publication recipe.

```bash
P=experiments/own-xpu-runtime/stage2/packet59b-int8-head
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build.py" device
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build.py" gnu-host
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/seal.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/seal.py" --verify
```

The CPU gate retains raw logits, scales, codes and proposals across two fresh
processes, checks fixed-tree reference equality, zero/tie/nonfinite cases,
and compares miniature target layer fixtures against the packet56 binary.
Two small rank0-draft integration runs also check target bytes and proposal
determinism. These are synthetic CPU tests; device determinism, acceptance,
full-model output identity and speed remain coordinator work.

[Screen command](WINDOW.md). [Task note](../../../../notes/2026-10-17-own-runtime-packet59b.md).
