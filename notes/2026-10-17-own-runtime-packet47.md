# Packet47: QSA decode attention, CPU preparation

The new packet is built, CPU-tested and sealed for the coordinator's physical
card-0 windows. **No GPU program or health probe ran. Device exactness and the
3x/5x speed bars are pending.** Packet45, packet46, the a367 packets, driver,
model payloads and protected runtime trees are unchanged. No service, power,
memory, swap, page-cache or reboot action was taken.

Packet: [packet47-qsa-attn](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/README.md).
The kernel, CPU oracle and analysis were developed separately, followed by an
[independent review](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/REVIEW.md).
All builds/tests used nice 19, CPUs 4–15,20–31 and Python without bytecode.

## What is slow

Packet46's selected M=1 control spends about **1513 µs on scores/softmax and
857 µs on values**, totaling 2370 µs at 4K. It puts all scores in only 24
32-lane work-groups. Each lane computes entire 256-dimensional dots in private
arrays, and each head scans the selected scores sequentially for its maximum.
The value pass has 6144 groups, but adjacent lanes fetch different tokens
instead of adjacent value dimensions. Every group also rescans the selected
IDs. There are no floating accumulation atomics; the error flag uses integers.
Private-array spills are a risk, not a measured finding.

The two KV heads are shared by 24 query heads. Selection ranks four-token
pools, takes up to 512 pools and appends the last 0–3 unpooled tokens: at most
2051 selected tokens. Power-of-two M=1 contexts at 2K and above select 2048.
The full bytes/FLOPs table at 1K/2K/4K/8K/32K is in
[ANALYSIS.md](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/ANALYSIS.md).
At 4K the ideal unique-data memory floor is 7.71 µs under the stated
550 GB/s assumption; charging KV separately to all query heads gives 91.6 µs.
Neither is a measured achievable latency.

Selection spends 171.6 of its 180.2 µs ranking pools. Ranking is quadratic in
populated pool count; the token cap does not cap that work. Qgate is a large
12288×2560 expanded Q6_K projection: roughly 39.3 MB of useful weight reads
in 113.3 µs, already about 347 GB/s. Both are measured by the new windows but
kept unchanged; attention is the larger lever.

## Two independently specified choices

The ordered candidate preserves the old addition tree and its probability
normalization before multiplying values. It distributes dots over selected
tokens and uses contiguous vector loads for KV. Fixed 32-token value tiles
retain every old odd-tail addition, then combine with the old tree. Admission
is done once per row. The full attention cost includes five kernel events.
**Order can be preserved; at least 5x has not been demonstrated.** If both
fresh timing owners reach 5x, prefer this path and retain the old oracle.

The alternative uses fixed selected-index splits of 32. Each split produces
its maximum, exponential sum and weighted values; a fixed upper tree rescales
and combines them. Including admission, it has three kernel events. The
split boundaries and arithmetic never depend on hardware occupancy, group
scheduling or card count. It has a separate proposed oracle identity,
`iq3-p47-qsa-split32-v1`; the record oracle remains unchanged. The
[oracle specification](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/ORACLE.md)
records all rounding boundaries and the October 11 precedent.

This is an operator packet. The new identity is not a full-model oracle or
an accepted lossless model result. After operator qualification, full CPU
reference/logit/token qualification and fresh full-engine repeats are still
required before adoption. No logits or answers were computed here.

## CPU results and retained evidence

Four fresh processes, GNU twice and Intel twice, each passed **36 cases and
299,230 checks**. Every process retained the same 294,912 output values and
raw byte stream. The tests cover both M values, all five requested contexts,
changing inputs, 2051-token tails, short reduction boundaries, signed zeros,
large finite scores and every old-tree length from 1 to 2051.

The old arithmetic matches the inherited CPU oracle. The blocked ordered
arithmetic matches it exactly, including pre-gate binary32 bytes. Split32
matches a separately scheduled recursive CPU implementation exactly.
Across the synthetic fixtures, old versus split32 differs in **55/294,912
BF16 outputs**, maximum absolute difference **0.001953125**, maximum
**131072 float32 ULPs** after decoding BF16 (two ordinary BF16 steps).
Before gating, maximum absolute difference is **1.192092896e-7** and maximum
float32 ULP distance is **103587**, sensitive to near-zero cancellation.
These differences are information, not an acceptance tolerance.

The eight Python tests pass, including a complete coordinator rehearsal with
real source/artifact seals, environment construction, binary identity and
316-capture parsing. Only external process/device/journal observations are
mocked. Negative tests reject missing/duplicate captures, contradictory
hashes, missing kernel events, bad timestamps, changed identities and
unsafe supervision. The independent reviewer verified the fixed trees and
resolved launch selector, event accounting, output poisoning and layout issues.

[CPU receipt](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/cpu-gates.json),
[compile-only device receipt](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/build-device.json),
[Python receipt](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/python-gates.json).
Raw output SHA256 across all four CPU processes:
`5385552dd407f8a6196f3fca7c74cdd7adac1ce1052ad80478fa4fe27561aa01`.

The final seal binds 40 source/evidence inputs and 15 artifacts:
`4581c5e14d8a5dbd553193eeb594cc118b1d4bc2109489c41581f9bc14e5beaf`.
The approximately 520 KiB device binary is
`c2818fa38ca93d2fab049612499815fe86ae7f18006b6f773bef201bced34e03`.
New build products total under 1 MB; four 1.4 MiB compressed raw CPU streams
are retained with [rationale and restoration](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/ARTIFACT-RETENTION.md).

## Coordinator handoff

The exact copyable E1, E2, T1 and T2 commands are in
[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/WINDOW.md).
They run through `coordinator-exact.sh` / `coordinator-timing.sh` in separate
single-attempt systemd user units. Every window is physical card 0, checked
by PCI address, under one seal and the coordinator's current reviewed fault
boundary. There is no queue launch or device authorization implied by CPU prep.

E1/E2 each require 316 raw-byte comparisons and identical fresh-process
identities. T1/T2 each cover 1K/2K/4K/8K/32K, M=1/M=2, ten warmups and 200
measured pairs per shape, all three variants. Every timed attention, selection
and qgate output is checked against CPU bytes outside measured events. All
required event endpoints and per-class totals are retained. At M=2, the
control is two sequential p30 attention calls; candidates batch the two
causally distinct rows. Side M=2 selection/qgate are batched operator
measurements, not the engine's sequential full-layer dispatch.

The preregistered bar is **3x attention at 4K for M=1 and M=2 in both fresh
owners**. Prefer ordered if it reaches **5x**. A correct but slower result
remains a recorded negative. Malformed second-row batch behavior can differ
from sequential partial writes; future integration must preserve fail-closed
handling. Nonfinite model-input behavior is not qualified by the finite gate.

## Estimated suite effect, not a measurement

The actual twelve suite prompts are **60–90 tokens**, mean 71.8333. During
128 generated tokens they reach only **187–217 occupied tokens**. Capacity
4096 does not make them 4K prompts, so 12 times the measured 4K saving is not
a valid suite estimate.

The conditional model scales variable work by selected count and explores
fixed costs of 0/50/100 µs with hypothetical 3x/5x variable-work improvements.
It assumes no new fixed cost, so it can be optimistic for extra launches.
For the 50 µs/3x illustration, mean attention time over the 99 scored decode
intervals is **188.027 → 96.009 µs per layer**. Twelve serial layers would
save **1.104 ms/token**, or seven rank-1 layers alone **0.644 ms**. At 5x,
the corresponding per-layer after value is 77.605 µs.

This gives an illustrative **40.4–41.6 tok/s** sensitivity around the supplied
39.42 record, not a forecast or a recomputed class-median result. MTP misses,
overlap, acceptance changes, new launch overhead and one-card expert stalls
remain unknown. Full per-prompt/per-position before/after values are retained
for all 128 positions in the
[CSV](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/analysis/per-position-estimate.csv),
with [assumptions and source pins](../experiments/own-xpu-runtime/stage2/packet47-qsa-attn/analysis/estimate.json).
No after timing, logits, end-to-end speed or one-card throughput was measured.
