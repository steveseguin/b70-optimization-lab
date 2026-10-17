# Packet48: decode GEMV bandwidth, CPU preparation

Packet48 is built and sealed for the coordinator. **No GPU program ran here.**
Both compilers pass the arithmetic checks and both fresh CPU repeats. The
candidate changes the weight layout and loading, while keeping each output's
arithmetic order. Whether it saves time remains unmeasured.

Packet: [packet48-gemv](../experiments/own-xpu-runtime/stage2/packet48-gemv/README.md).
The main-only tree was pulled before work; the first census/preregistration
commit is `04c337891`, pushed immediately. Packet47's directory and packet45's
sources/builds were not changed. All sustained preparation used nice 19,
CPUs 4–15,20–31 and Python `-B`; compilation was serial. New build artifacts total
about 2.2 MB, including retained failed binaries. Root still has about 23 GB free.
No model payload, service, GPU health probe, sudo, power, memory, swap or cache
setting was used or changed. Existing device ownership stays with the coordinator.

## Bytes, bandwidth and priority

The [reproducible census](../experiments/own-xpu-runtime/stage2/packet48-gemv/BYTE-CENSUS.md)
and [source-pinned JSON](../experiments/own-xpu-runtime/stage2/packet48-gemv/byte-census.json)
derive shapes/types from the tracked GGUF table and timings from packet46's
card 0 M1 receipts. The release's IQ3_XXS name does not describe every tensor:
ordinary gate/up is IQ2_S, down IQ4_NL, and only layer 2 gate/up is IQ3_S.
Q6/Q8 dense weights are already expanded to signed bytes plus FP32 scales.

Decimal MB; unique useful weight bytes, **not measured DRAM transactions**.
M2 means two distinct input rows. Its expert union depends on route overlap.

| Class | M1 MB | M2 unique MB / current serial read MB | M1 µs, T1 | Useful GB/s | Gap to 550 GB/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Routed gate/up pair | 10.496 | 10.496–20.992 /20.992 | 81.875 | 128.2 | 421.8 |
| Routed down | 9.216 | 9.216–18.432 /18.432 | 91.875 | 100.3 | 449.7 |
| GDN QKV | 32.768 | 32.768 /65.536 | 100.105 | 327.3 | 222.7 |
| GDN Z | 19.661 | 19.661 /39.322 | 39.740 | 494.7 | 55.3 |
| Attention output/combine | 19.661 | 19.661 /39.322 | 57.605 | 341.3 | 208.7 |
| Small FFN, including router matrix | 9.349 | 9.349 /18.698 | 27.812 | 336.2 | 213.8 |
| Shared down | 1.843 | 1.843 /3.686 | 11.041 | 166.9 | 383.1 |
| HC set, including non-GEMV work | 15.155 | 15.155 /30.310 | 134.166 | 113.0 | 437.0 |
| Route softmax/ranking | 0 weight MB | 0 /0 | 43.438 | not a weight GEMV | not applicable |

Route's minimum operand traffic is 6,072 B/M1 and 12,144 B/M2; its source loops
express much more repeated cached traffic. The router matrix is already counted
in small FFN. The JSON separately gives packed allocation bytes, expanded row
strides, activation/output traffic and repeated source-level loads. No M2
timing or bandwidth is inferred from M1.

Subtracting the hypothetical 550 GB/s weight time gives optimistic aggregate
gaps: experts **6.557ms** over 47 ordinary gate pairs plus 48 down layers; HC
mixed work 5.117 ms; Q6 QKV 1.418 ms over 35 layers; output/combine 1.049 ms over 48;
small FFN 0.508 ms over 47; shared down 0.369 ms over 48; Q6 Z 0.140 ms over 35.
HC and route include reductions/launches, so their gaps are not GEMV forecasts.
The priorities are experts first, then QKV. Z has only about 4 µs/M1 of
weight-floor gap, although M2 weight reuse may be valuable.

## What the candidate changes

The [kernel design](../experiments/own-xpu-runtime/stage2/packet48-gemv/KERNEL-DESIGN.md)
records the source diagnosis. IQ2/IQ3/IQ4 block pitches 82/110/18 bytes misalign
fields despite an aligned allocation. The old expert decoder uses repeated
metadata/table loads; dense and selected down paths spell many contiguous
loads as scalars. Each SG32 lane has a serial eight-product chain per tile.
Normal GEMV does not use atomic accumulation; fused sticky-error atomics are
an invalid-route path. Actual occupancy, spilling and the limiting instruction
mix remain unmeasured; source counts cannot prove those bottlenecks.

The new checked load-time repack separates fields into aligned compact planes.
IQ2 rows grow 820→832 B, IQ3 1100→1120 B, IQ4 360→368 B. Q6/Q8 rows omit unused
retained metadata, 3380→3200 B and 3040→2880 B at K=2560. Native loads use aligned
16/32-bit fields and contiguous BF16 input vectors; paired gate/up shares its
input loads. No weight is requantized or fully expanded into FP16/FP32.

M2 has independent inputs and routes. Equal expert-row addresses at the same
slot share decoded values; shifted overlapping routes do not yet share across
slots. The timing reports separate identical, overlap-five and disjoint cases.
Dense M2 shares decoded weights across both inputs. This is reuse, not
compute/compute overlap: B70 has one CCS.

All admitted outputs keep lane `8*l+256*t`, increasing `j=0..7`, separate
multiply/add, SG32 adjacent-pair reduction and BF16 storage. Ordinary QKV/Z
use Split1. Additional CPU tests cover the old Split4 tree unchanged. No
oracle-changing variant is implemented. A new reduction would need its own
matching CPU reference and separate qualification.

One genuine negative result is retained. Unrestricted nonfinite weight scales
changed NaN payload selection under GNU and Intel. The revised repacker rejects
those scales **before writing**; it does not canonicalize them. Finite scales,
signed zeros and nonfinite activations remain strictly tested. Future loading
must check actual model scales and keep the old path for a rejected bank.
[Failure and retained sources](../experiments/own-xpu-runtime/stage2/packet48-gemv/NONFINITE-CLOSEOUT.md).
This packet has not scanned the model to assert its admission.

The actual expert controls are the inherited P39 IQ2/check and IQ4/status
kernels. IQ3 and dense controls use their unchanged current lane functions in
equivalent isolated SG32 wrappers, including 32-bit control offsets. Their
timing still needs whole-engine confirmation. IQ3's separate packet18 check
is excluded and cannot satisfy the ordinary IQ2 performance bar.

## CPU gates and coordinator handoff

- GNU and Intel: **503,656 arithmetic/rejection checks per process**, twice
  freshly under each compiler. Includes decoded FP32 values, all lane sums,
  five different consecutive rows, paired gate/up, M2, both dense trees and
  rejected nonfinite scale encodings with untouched destinations.
- Complete CPU harness: **126 cases/process, four fresh processes,504 total**;
  seven classes × two M values × nine inputs/control cases. Output/status/error
  bytes and fresh-process hashes agree. CPU rows are miniature; native fixtures
  use production sizes and 512 experts. Device geometry still needs E1/E2.
- **16 protocol/mutation tests** pass; exactness companions, event coverage,
  source/binary/gate seals, fresh process identities and teardown fail closed.
- SYCL binary compiles; it was **not executed**.

[CPU gate receipt](../experiments/own-xpu-runtime/stage2/packet48-gemv/cpu-gates.json),
[protocol receipt](../experiments/own-xpu-runtime/stage2/packet48-gemv/python-gates.json),
[review](../experiments/own-xpu-runtime/stage2/packet48-gemv/REVIEW.md),
[seal](../experiments/own-xpu-runtime/stage2/packet48-gemv/seal.json).
Final seal SHA256:
`75171f07f80df76d99c86d15908f403dff0d75a1990e76707f681052d04ee3a1`.
Device binary SHA256:
`ab1c40a369daaacd44e9f449523c3e94e74c35986e2bb78874ebf7534c895188`.

The [exact script-file window commands](../experiments/own-xpu-runtime/stage2/packet48-gemv/WINDOW.md)
run E1, E2, T1 and T2 under separate coordinator-owned user units. Native
admission checks physical LevelZero0 is PCI 0000:23:00.0 before context creation.
It never equates this with DRM card0. The wrapper preserves cooperative-only
teardown, journal polling, memory/storage admission and a retained-child latch.

Each timing owner alternates old/new over 24 measured changing-input pairs
after four excluded initialization iterations, at both M values. Both must
meet **1.5× on the IQ2 gate/up+down sum or 40 µs saved across the four ordinary
GDN GEMV classes at M1**. A control deviating over 15% from packet46's matching
class withholds in-layer qualification. M2 cannot pass an M1 bar. No full-engine
or public throughput claim follows from passing these operator windows.

## Conditional two-card effect

At the 1.5× expert bar, packet46's 173.75 µs ordinary expert sum becomes 115.83 µs,
saving 57.92 µs/layer. Across the SPEED6 split this is about **1.27 ms for 22 ordinary
layers on rank 0 and 1.45 ms for 25 on rank 1 per target position**. Layer 2's IQ3/Q8
exception needs its own timing; granting it the same saving would be an
assumption. If gains transfer uniformly, this is only roughly a 42 tok/s planning
scenario versus 39.42, using the roadmap's hit/miss model, not a measured result.

The alternative 40 µs ordinary-GDN bar applies to 17/18 matching Q6 GDN layers,
about **0.68/0.72 ms per half**, plus separately measured QSA expert and Q8-layer
savings. Do not multiply this whole-GDN result by all 48 layers. Two pipeline
halves overlap; their savings cannot simply be added into an emitted-token
rate, and rank 0 speculation/redo, draft work and head time remain.

Full expert padding adds about 886 MB across the model before dense savings.
A later integration must replace old banks and prove per-card fit/reserves;
it cannot keep both full copies as this isolated comparison does. Current
record 39.422009 tok/s remains unchanged. The next step is the coordinator's
byte gates, then both timing owners; this preparation grants no GPU ownership.
