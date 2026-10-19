# 2026-10-19: packet177, a structural two-card plan (CPU only)

Packet: `experiments/own-xpu-runtime/stage2/packet177-twocard-structural/`
([PLAN](../experiments/own-xpu-runtime/stage2/packet177-twocard-structural/PLAN.md),
[options.json](../experiments/own-xpu-runtime/stage2/packet177-twocard-structural/options.json),
[price.py](../experiments/own-xpu-runtime/stage2/packet177-twocard-structural/price.py),
[DO-NOT-REPEAT](../experiments/own-xpu-runtime/stage2/packet177-twocard-structural/DO-NOT-REPEAT.md)).
No device work, build, queue or packet change. No model bytes were read.

## Why

The two-card record has been 58.798109 tok/s (bundle 8) for about 18 hours.
Every lever on the current structure is closed or below +1%. This study asks
whether a different two-card structure can do better.

## What the evidence says

Bundle 8 already keeps both cards busy. A hit interval of 14.70 ms is the
draft (1.60) plus rank1's body and head (13.09). Rank0's next-A (12.48) plus
its head suffix runs alongside. A miss costs 25.61 ms.

| Option | Single-user ceiling | Verdict |
|---|---|---|
| (a) Exact tensor parallelism inside each layer | +2.9% only at a 3.3 µs/phase device-copy floor with no split costs; −5% to −32% with real costs | **Closed** (p45 already rejected it; this is the re-price on bundle 8) |
| (b) Placement, pipeline depth, interleave | +2.9% ceiling; every measured move lost | **Closed** |
| (c) Lossless dense byte cut: **S1, read the retained fp16/int8 scales** | **+3.7%** (Q6 bytes −14.4%) | **Open: the recommended build** |
| (c) 6-bit packed codes (S2/S3) | +5.2% / +9.3% byte bounds | Needs a new unpack mechanism (p74 lost) |
| (d) Two sequences in the pipeline | about 76 tok/s aggregate (about 95 with M=2), not single-user | A second metric only; neural.download profile, not a LocalMaxxing record |
| (e) Host wait / copy engine | +0.6% even if all stalls vanish | Nothing to port; two cards already spin and have no fills |

Tensor parallelism fails for a simple reason. It removes the speculation tax:
the draft on the critical path plus about 2.35 ms per token of miss redo. But
it has to repeat about 7.4 ms of latency-bound work on both cards (HC, router,
shared expert, mixture), and it needs 144 dependent cross-card gathers per
token. The cards have no idle time for it to reclaim.

## The recommendation: S1 metadata-scale dense lane

**What changes.** Every expanded Q6_K row still carries the original fp16
super-scale and 16 int8 sub-scales per 256 weights. That is 18 bytes, against
the 64 bytes of FP32 scales that the fast loop reads now. S1 reads the
18 bytes and recomputes `half(d) * float(sc)` in the kernel.

**Why it is exact.** That expression is the same single FP32 multiply the
loader used, so the bits are identical for every finite `d`. A startup census
refuses on any mismatch.

**Cost and value.** Dense GEMV bytes drop 14.4% for one multiply per 8-weight
step. Dense is two-thirds of the token and bandwidth-bound: packet175's
prefetch made it 1.44× slower because extra bytes cost time.

**Novelty.** p74 paid for a per-weight 6-bit unpack. D1 only shares the same
FP32 word between lanes. No packet has read this metadata.

**First kill test.** A one-card lane-B micro on packet175's harness. It uses
real layer 0 and layer 3 tensors and compares A (production), B1 (S1a, no
storage change) and B2 (S1b, FP32 d + int8 sc written at load). Every output
byte must equal arm A, and the scale census must find 0 mismatches.

| Weighted covered dense GEMV time B/A | Decision |
|---|---|
| ≤ 0.93 (about +2%) | Build |
| 0.93–0.96 | Bundle with D1 and p153 only |
| > 0.96 | Close, with a DO-NOT-REPEAT row |

**Flag.** `--dense-scales expanded|metadata`, default `expanded`. It is
wired the way packet173 requires for process-wide flags.

**Time.** About 1.5 h CPU prep and 15 min of device time for the micro. If it
passes, about 4–5 h CPU and 1.5 h device for the build and brackets.

## Next

1. Prepare the S1 micro as packet177b. It reuses packet175's micro and
   evidence pattern, and its readiness marker is written last.
2. If it passes, build the flag, kernel, census and bracket per PLAN §5.
3. Separately, the owner may want the two-sequence profile for neural.download.
   It needs no new kernels.
