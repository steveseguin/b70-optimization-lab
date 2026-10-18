# Draft formats and candidate costs

Publisher: Qwen/Qwen3.8-Flash-Next-FP8, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. The local `mtp-manifest.tsv`
pins all 3,101 draft tensors, individual payload hashes and shard stat identity.
`mtp36::Store::read` checks those bindings before returning each tensor.
No weights were downloaded. Local publisher provenance is recorded in
`../packet1/identity.json`; the target's Unsloth GGUF authority remains unchanged.

| Component | Publisher | Production draft |
| --- | --- | --- |
| 512 routed experts, gate/up/down | FP8 E4M3, BF16 scale per 128×128 block | INT8, symmetric nearest-even requantization, FP32 scale per 16 values |
| Attention Q/K/V/O and indexer | BF16 | Same BF16 bytes; combined indexer split into Q/K views |
| Shared expert and router | BF16 | Same BF16 bytes |
| HC down/up/injection and merge projections | BF16 | Same BF16 bytes |
| Norm weights | BF16 | Existing widened FP32 `1 + weight` convention |
| Embedding | Publisher BF16 | Target GGUF embedding decoded to BF16 |
| Head | Publisher BF16 | Shared target expanded Q6_K, only 80,128 draft rows; full target head unchanged |

The source of truth for these conversions is `mtp.hpp`: `requant`, `load`,
`compute`'s embedding lookup, and head initialization. Current selection uses
production expert kernels, not packet59's alternative expert reduction.

Every expert matrix has 1,638,400 scalar weights. There are 1,536 matrices.
Totals below exclude unchanged attention, HC and scratch allocations.

| Candidate | Expert storage bytes | Change from INT8 | Expected draft-time effect (unmeasured) |
| --- | ---: | ---: | --- |
| Production INT8 + FP32 group16 scales | 3,145,728,000 | 0 | Control |
| Exact FP8 + original block scales | 2,516,889,600 | −628,838,400 | 20% fewer expert weight bytes, plus FP8 decoding instructions; net unknown |
| Exact FP8 + per-row repeated BF16 block scales | 2,555,904,000 | −589,824,000 | 18.75% fewer expert weight bytes; same multiply/reduction order, extra decode instructions |
| FP8 product rounded to BF16 | 5,033,164,800 | +1,887,436,800 | 60% more bytes and an extra rounding; exceeds current rank1 arena margin |
| FP8 product stored as FP32 | 10,066,329,600 | +6,920,601,600 | 220% more bytes; does not fit |

The preregistered diagnostic uses the exact FP8 per-row format, with all ten
selected experts staged in each of three private banks. That costs
**49,920,000 bytes**, independent of expert IDs. Publisher tensor reads are
authenticated again at staging. Production INT8 weights remain resident.
The shadow pays host reads, hashing, uploads, a second suffix and full mutable
state restoration checks; none of its timings predicts a production speed.

A separate BF16 publisher-head prefix would cost **410,255,360 extra bytes**
because the shared target head must remain. Its raw prefix reads are about
1.515× production's expanded-Q6 row bytes. It may also require the publisher
embedding to avoid mixed checkpoint fidelity. Neither is selected here; expert
fidelity is isolated first. A new candidate needs a new independent decision.

At the supplied historical 13 ms miss penalty, +1.5 acceptance points can pay
about **0.195 ms per generated token** of additional draft work. This is a
planning estimate, not a measured gain. Even a passing acceptance diagnostic
must earn a net-positive matched timing bracket before adoption.
