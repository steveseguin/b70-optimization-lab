# 2026-10-19: packet175, D2 warm-ahead device micro (CPU preparation only)

Packet: `experiments/own-xpu-runtime/stage2/packet175-twocard-d2-micro/`.
No device work has run. Nothing is queued.

## Why

The packet168 v3 census puts dense_hc at **11.532 ms** per two-card body pass,
summed over both ranks (5.574 + 5.955). Packet173 ranks D2 first: a dense-weight
L2 warm-ahead, estimated at +0.85 / 1.71 / 3.03%. Its pre-registered rule required
a device micro before any ~4 h integration.

**Decision rule.** Coordinator hourly review 44 changed the rule before sealing.
The micro measures the weighted dense GEMV time **B/A**, with the warm-ahead kernels
included in B:

* **B/A ≤ 0.97:** "eligible for combined bundle-9". D2 is built only together with
  packet153's static descriptors (+0.35%, exact), never alone.
* **Otherwise:** "close D2", and the analyzer writes a DO-NOT-REPEAT row.

## Design

* **Code.** packet166's M1 layer path, which passed on lane B today with
  `cpu_oracle_match` true. It uses the same private native closure, the real layer 0
  (GDN) and layer 3 (QSA) weights including the 512-expert banks, position 31, and
  rows 0 and 1.
* **Arm A:** baseline.
* **Arm B:** the same launches, plus a warm-ahead kernel before each dense GEMV. The
  kernel loads one 32-bit word per 64-byte line of each weight tensor that GEMV
  reads, and writes nothing.
* **Arm B′:** the warm-ahead time alone.
* **Repeats.** 240 interleaved AB/BA pairs per layer.
* **Realism of L2 eviction.** The real launch order runs between GEMVs: HC, the
  projections, GDN/QSA, the routed experts and the shared expert. A 256 MiB
  stream-read interposer before each row stands in for the rest of the token.
* **Exactness.** Arm B must be byte-identical to arm A, proof buffers included. Every
  timed arm is checked against the reference outside its timing events.
* **Lanes.** There are proposals for lane A (card 0) and lane B (card 2), with job
  names `packet175-d2-warm-ahead-micro-A1` and `-B1`. Run only one; the runner refuses
  a second lane once either output exists.

## CPU gates passed

* **Builds.** Three builds through `ops/compile_turn.py`: GNU host, Intel host and
  device. Three turns were used in total:
  * the first built GNU only, as a compile check;
  * the second built all three;
  * the third rebuilt all three after a fix. The first CPU gate refused with "warm
    span" because 1-D weights such as `ffn_gate_inp_shexp` have `rb=0`. The warm-ahead
    span now uses the whole weight allocation. The refused trace directory was
    removed before the rerun, so it is not retained.
* **CPU parity.** With synthetic weights, GNU equals Intel and host arm A equals arm
  B. All 138 packet166 buffers at position 31 equal packet166's own synthetic trace.
* **Oracle.** As a result, packet166's real-weight oracle (138 rows at position 31)
  is inherited by digest reference. There were no GGUF reads.
* **Preparation.** 964 real CPU-transport resets in the Landlock sandbox, with
  `ionice -c3` checked. Seven analyzer tests pass.
* **Rehearsal.** `lanequeue plan` passed on temporary copies of the A and B queues.
  `run_micro.py --plan` passed for both lanes. The private report adapter ran the
  real report entry: the boundary B/A = 0.97 came out eligible, 0.9705 and a 25%
  regression closed, the invalid oracle was refused, and the packet166 stream was
  rejected.

## Caveats

* **Projection kernels.** The large projections are packet166's lab-owned dense lane
  plus finish, not `main.cpp`'s sealed-selection dispatcher. In packet166's device
  stream at M1, dense took 0.325 ms per row in GDN layers and 0.556 ms per row in QSA
  layers. Weighted over 36 GDN and 12 QSA layers, that is about 18.4 ms per body pass,
  against the census 11.5 ms. These GEMVs are therefore less efficient than bundle 8's.
* **Direction of the bias.** If anything, this flatters warm-ahead, because
  latency-bound GEMVs gain more from L2 hits. An "eligible" result still has to pass
  the combined bundle-9 v5 bracket. A "close" result is robust.
* **No overlap.** The warm-ahead here is a separate serial kernel. The B70 has one
  CCS, so the kernel cannot overlap the GEMV, and it pays its own DRAM read.

## Next

The coordinator admits one proposal on whichever lane is free. After the run, read
`evidence/d2-micro-<lane>1/analysis.json`.

## Device result (coordinator, 2026-10-19 11:22–11:24 UTC)

`packet175-d2-warm-ahead-micro-B1` ran on lane B, card 2, and finished DONE. A and B outputs were byte-identical, and the fault count stayed 2.

| Layer | Dense A ms/row | B GEMV only | Warm-ahead alone | B incl. warm-ahead | Reduction (median) | GEMV-only reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 (GDN) | 0.300 | 0.255 | 0.198 | 0.453 | **−50.9%** | +15.0% |
| 3 (QSA) | 0.555 | 0.524 | 0.210 | 0.734 | **−32.2%** | +5.5% |

Weighted B/A is **1.439**, against a gate of ≤ 0.97. **Decision: close D2.** Prefetching makes the GEMV itself 5.5–15% faster, but the separate warm-ahead kernel re-reads the same weight bytes from DRAM. That costs more than the GEMV saves, because the card is bandwidth-bound and the single CCS cannot overlap the warm kernel with other compute. Any variant that reads the weights twice is dead for the same reason. Only a prefetch that is free in bandwidth terms could change this, and on a bandwidth-bound card there is no such slot.
