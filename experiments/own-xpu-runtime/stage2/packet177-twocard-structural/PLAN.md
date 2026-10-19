# Packet177 — structural two-card decode plan

2026-10-19. CPU-only study. No build, GPU, service, sudo, setting, queue, or
existing packet was touched, and no model bytes were read. Every number below
is labelled **measured** (a retained device receipt on this IQ3 line),
**transferred** (a device receipt from another identity, such as an older
bundle, a synthetic layer micro, or a transport-only harness), or **assumed**.
Percentages are conditional planning numbers against the record's pooled
interval mean. They are not speeds.

Record: **58.798109 tok/s**, packet136 bundle 8. Unsloth UD-IQ3_XXS
("quantized compressed version"), two B70 cards (2 and 3), single user, greedy,
exact against `iq3-p49-split32-v1`, full BF16 KV and state.
Reproduce every number with `python3 -B price.py --write`, which writes
[`options.json`](options.json).

## 1. Decision

**Single user:** none of the layer-structure options, (a) tensor parallelism
or (b) placement/depth, can reach +3%. Even their fantasy ceilings stay under
+3%, and every one of them that has been measured lost. The one structural
option still open is **(c) a lossless change to how the dense weights are
read**. The build is **S1, "metadata-scale dense lane"**.

S1 makes the dense GEMV read the original fp16 super-scale and int8 sub-scales,
which every expanded Q6_K/Q8_0 row already carries in its trailing metadata.
Today it reads the 4-byte FP32 scale per group instead. Q6 dense bytes drop
from 1.25 to 1.0703 B/weight (−14.4%, measured from the format). The extra work
is one fp16→fp32 conversion and one FP32 multiply per 8-weight lane step,
with no 6-bit unpack. The ceiling is **+3.7%** in dense_lane scope, or +4.1%
if the HC Q8 kernels are converted too. That assumes 85% byte→time transfer.

The first step is a one-card device **kill micro**, with a go/no-go threshold
on the weighted dense GEMV time (§5).

**Second metric only:** (d) a two-sequence pipeline gives about **76 tok/s
aggregate** (modelled, 38 per user), or about 95 with M=2. It is exact by
construction. LocalMaxxing withholds aggregate throughput, though, so it can
only be a neural.download concurrency profile. It is not the recommended build.

## 2. The current structure (bundle 8, `packet173-twocard-lever-table/base/`)

* **Two processes,** rank0 on card 2 and rank1 on card 3. Each has one
  in-order compute queue. Waits are pure spin (`P56X_SLEEP20=0`). Placement
  is `[1,0,24]`, a 24/24 layer split (`bundle-selection.json`).
* **Speculative pipeline.** Rank1 runs the MTP draft D, then body B: layers
  24–47, the target head prefix, and the suffix merge. Rank0 runs next-A
  (layers 0–23 for the guessed next token) and the 46,080-row head suffix.
  The draft head uses the fixed 80,128-row prefix.
* **Interval** (packet160, measured, 1,188 record intervals):
  `T = max(D, R+C) + max(B, A+offset) + G`.

| Measured, ms | Hit (932) | Miss (256) |
|---|---:|---:|
| D (rank1 draft) | 1.597 | 1.596 |
| R / C (restore / rank0 redo of A) | 0 / 0 | 0.551 / 11.819 |
| A (rank0 next-A) | 12.482 | 12.486 |
| B (rank1 body + head + merge) | **13.086** | 13.230 |
| Interval | **14.704** | **25.613** |

The pooled mean is 17.055 ms; the record metric is equivalent to 17.007 ms.
B wins every second race, and D wins every hit readiness race. Rank0 waits
about **1.23 ms per interval** for the draft (packet154, measured). On misses,
rank1 idles for about 10 ms while rank0 redoes A.

The speculation tax is the D on the critical path plus about 2.35 ms per token
of miss redo. A structural change would need to remove that tax without paying
more elsewhere.

**Census v3** (packet168, measured, ms per body pass summed over ranks):

| Class | ms | rank0 / rank1 |
|---|---:|---|
| dense_hc | 11.532 | 5.574 / 5.955 |
| routed_experts | 5.535 | 2.564 / 2.973 |
| router_shared_expert | 3.341 | |
| gdn | 2.050 | |
| norms_glue | 1.835 | |
| residual | −7.158 | overlap; not isolated |

**Dense weight formats** (measured, packet110 `BYTE-MODEL.md`;
`packet10-kopt5/expanded.hpp`). Load-time expansion is not a
re-quantization.

* **Q6_K:** GDN QKV/Z, the attention output projection, the QSA Q/gate, K
  and V, and shared gate/up/down. Expanded row:
  `K` int8 codes + `4K/16` FP32 scales + `18K/256` retained metadata.
  The metadata is the fp16 `d` and 16 int8 sub-scales per 256. For K2560 the
  row stride is 3,380 B, and the fast loop reads 3,200 B.
* **Q8_0:** HC low/up `[320×10240]`/`[10240×320]` and the layer-2 exceptions.
  Expanded row: `K + 4K/32` + a retained 2 B fp16 `d` per 32.
* **F32:** router, alpha/beta, and HC inject. Unchanged here.
* `p33::dense_lane` (`base/p33_candidates.hpp:76-100`) reads
  `scale = bits_float(u32(w + K + 4*(tile/group)))`. The loader produced that
  word as `half(d) * float(signed8(sc))` (Q6) or `half(d)` (Q8)
  (`expanded.hpp:33-41`).

## 3. What was already tried (DO-NOT-REPEAT sweep)

I grepped all 214 stage2 `DO-NOT-REPEAT.md` files and the related notes for
TP / all-reduce / peer / P2P / split GEMV / column / row split / pipeline depth
/ placement / micro-batch / 3- or 4-card / transfer.

| Attempt | Outcome | Why it closed |
|---|---|---|
| packet12 peer transport (cards 2+3) | **measured:** 10 KiB peer copy 18.3/18.6 µs wall, 3.3 µs device event; 60 dependent rounds 52.3 µs/round (host bounce 166.6) | transport-only; no model quality |
| packet14 tp2 | exact on cards; 41 exchanges ≈ 1.53 ms/layer | too many exchanges |
| p45 within-layer split step 1 (10-15) | **REJECT**: exact proof of 3 data phases + 1 route check per layer (194 phases/token); 7.09 ms of exchange at measured copy medians; replicated HC/router/shared work 7.38 ms | the replicated work plus exchanges exceed the halving |
| packet160 a1–a3, b1–b2, c, d1–d4 | all < 3% (expert parallel inside B +1.9% ideal; whole-draft split +3.3% with zero communication) | B-race and draft dependencies |
| packet148 correction cooperation | row coop +1.04/+1.32%, head coop +1.57/+1.91% (sensitivities); moving a layer needs 1.13 GB against rank1's 0.786 GB margin | memory, state ownership |
| packet144 miss path | every mechanism < +3% | |
| packet120 25/23 | **measured −3.9%** (hits +0.59 ms) | rank0 has no slack |
| packet127 head rows to rank0 | **measured −1.95%** | same |
| packet79 draft on rank0 (23/25, 24/24) | **measured −2.3% / −1.3%**; misses +2.1 ms | the draft needs rank1's final state |
| packet71c depth-2 engine | **measured −46.8%** | M=2 verify cost |
| packet74 packed Q6_K/Q8 dense + head | **measured −0.8 / −2.4 / −2.9%**, exact | the in-register 6-bit unpack costs more than the ~34% byte saving |
| packet175 D2 L2 warm-ahead | **measured: dense 1.44× slower** | bandwidth-bound card; the prefetch re-reads bytes |
| packet156/158 draft line | ≤ +2.3% at full closure | draft near its roofline |

## 4. Priced options

### (a) Intra-layer tensor parallelism of the dense/HC GEMVs

This uses the p45 exact layout: output-row split, whole heads, ordered gathers,
and replicated HC/router/shared/mixture. It replaces the speculative pipeline,
so there is no D, no misses and no capture.

`T = (A + B − capture + R_repl)/2 + 144 × L_phase + split costs`

* Halved compute is **16.10 ms**. Inputs: A + B measured, capture 0.743
  measured, `R_repl` = 7.377 transferred.
* The break-even phase latency, with zero split overhead, is **6.62 µs**.

| Phase latency L | Source | Ideal | With split costs |
|---|---|---:|---:|
| 3.3 µs | transferred; packet12 device event only | +2.9% | −5.3% |
| 15.2 µs | measured; p87t bounce, idle | −6.7% | −13.5% |
| 18.6 µs | transferred; packet12 peer wall | −9.2% | −15.6% |
| 52.3 µs | transferred; packet12 dependent round | −27.8% | −32.0% |

Split costs are assumed: 0.75 ms of half-shape kernel floors, plus a
transferred 0.68 ms of expert imbalance.

**Closed.** It replaces the pipeline rather than composing with it, because
both cards are already busy on hits: rank0 runs A + suffix while rank1 runs
B. The about 7.4 ms of latency-bound replicated work per card cancels the
removed speculation tax. No transport, not even the 3.3 µs device floor,
clears +3%.

### (b) Different placement, pipeline depth, or interleave

* **Ceiling:** perfectly spreading rank0's 1.23 ms draft wait gives
  **+2.9%** at zero transfer cost.
* **Measured:** every move lost. 25/23 −3.9%, head rows −1.95%, draft on
  rank0 −2.3/−1.3%, depth-2 −46.8%.
* Finer interleaving or a third stage for one sequence needs depth ≥ 2
  guessing, which packet71c measured.

**Closed.**

### (c) Lossless dense byte reduction

The same bytes and values are kept. Only the read layout changes. Time
transfer `f = 0.85` is assumed, supported by D2: dense is bandwidth-bound.

| Variant | Q6 bytes | Q8 bytes | Extra ALU | Ceiling |
|---|---:|---:|---|---:|
| **S1a: read retained fp16 d + int8 sc** (no storage change) | −14.4% | −5.6% | fp16→fp32 + mul per 8 weights | **+3.7%** lane only / +4.1% with HC |
| S1b: load-time FP32 d + int8 sc in the old scale region | −13.7% | 0 | int8→f32 + mul per 8 weights | +3.5% |
| S2: planar 6-bit codes + FP32 scales | −20% | 0 | unpack per weight | +5.2% |
| S3: GGUF packing, free unpack | −34.4% | −5.6% | p74 measured a loss | +9.3% (byte bound only) |

**Exactness of S1.** The loader computed each scale as one IEEE FP32 product,
`half(d) * float(int8 sc)`. Recomputing it in the kernel with the same
`iq3::half` software conversion and the same single multiply gives identical
bits for every finite `d`. There is no add, so contraction cannot apply. The
product/add order of the lane, the split32 tree and the split4 finish are
untouched.

A non-finite `d` could differ in NaN payload between host and device (packet25
recorded such sign changes). So a startup census compares every recomputed
scale with the stored FP32 word and refuses startup on any mismatch.

**The metadata is present in bundle 8.** `base/arithmetic.hpp:41-44` takes
expanded strides from `packet10-kopt5/expanded.hpp:16-19`, which includes
`(k/256)*18` metadata bytes per Q6 row. Packet48's load-time repack, which
dropped the metadata (3,380→3,200 B), is not in the bundle-8 path.

**Novelty check.**

* p74 read packed codes. Its cost was the per-weight 6-bit unpack, which S1
  does not have.
* D1/p140 multicast the *same* FP32 scale word across lanes. That cuts load
  instructions, not DRAM bytes.
* p25 "scale hoisting" concerned IQ expert metadata.
* No packet reads the retained dense metadata in the fast lane.

**Open; this is the recommendation.**

### (d) Multi-user / batch, a separate class only

Two independent sequences fill the two stages with no guessing. Card 0 runs
layers 0–23 for X while card 1 runs 24–47 for Y, then they swap. Each sequence
keeps M=1 kernels, so it is bit-identical to single-user by construction.

* **Slot:** max(A − capture, B) + handoff = **13.10 ms**, giving **76.3 tok/s
  aggregate** and 38.2 per user (modelled from measured A/B).
* **Four sequences at M=2:** about **95 tok/s** (packet166 M=2/M=1 measured
  1.58–1.63, exact per row).
* **Memory:** about 88 MB per sequence per card, against 4.07 / 0.786 GB arena
  headroom (memory-plan, modelled).
* **Records:** `docs/localmaxxing.md` withholds aggregate `tokSOut`, so this
  publishes only as a neural.download "Aggregate concurrency profile".
  It has never been proposed or closed.

### (e) Anything else

* **e1, host wait / copy engine** (audit of `base/`).
  * Waits: two-card is already pure spin, with 0 voluntary switches per half
    (packet165, measured).
  * Queues: every copy (hidden export/import, stream handover, token uploads,
    snapshot SnapshotFlat) runs on the single in-order CCS queue.
  * Fills: there are none, so the one-card fill-behind-copy effect (packet174,
    1.07 ms/token) cannot occur.
  * Measured copy-related stalls: p154 transport 0.051 ms/interval, G
    0.021/0.013 ms. Removing all of them would give **+0.6%**. Nothing to port.
* **e2, 3- or 4-card:** a different GPU-count record class. One sequence over
  more stages needs depth ≥ 2.

## 5. Recommended build: S1 metadata-scale dense lane

**Flag:** process-wide `--dense-scales expanded|metadata`, default `expanded`,
which is bundle 8 byte-for-byte. Add `compact` (S1b) only if the micro picks
it.

Follow the packet173 "Process-wide selection" pattern:

* `main.cpp`: `Options`, the parse branch next to `--host-path`, the require
  block, and apply-once at Engine startup.
* `chain_pipeline.py`, `pipeline.py` and `window.py`: identity and resume
  fields.
* KD `draft_window.py`.
* `selection.json` and its SHA stay bundle 8's. The flag goes into window
  identity and receipts.

### Step 0 — kill micro (one card, lane B, about 15 min device; about 1.5 h CPU prep)

* **Harness:** packet175's `micro.cpp`, packet166's M1 layer path. It uses
  real layer 0 (GDN) and layer 3 (QSA) tensors, position 31, rows 0 and 1,
  both arm orders, two processes, and alternating repeats. Weights are 36 GDN
  + 12 QSA.
* **Arms:**
  * A: production `dense_lane`.
  * B1: S1a, reading `half(u16(w+K+4K/g+18*(t/256)))*float(int8(...))`.
    For Q8, `half(...)` per 32.
  * B2: S1b, FP32 d + int8 sc written into the old scale region at load.
  * Callers: the large split4 projections, the attention projection,
    `p39_fused.hpp:86-87`, the p49d small Q6 tuples, and shared down.
* **Exactness, must hold for every arm:**
  * every output byte of every dense GEMV equals arm A;
  * a device census of every Q6/Q8 dense group in layers 0 and 3 finds
    recomputed scale bits == stored FP32 bits, with 0 mismatches.
* **Go / no-go** on the weighted covered dense GEMV time ratio B/A, with all
  added work included:
  * **≤ 0.93 → GO.** This is about 0.57 census-ms, ≥ +2% projected.
  * **0.93–0.96 → bundle only** with D1 and p153 (+0.35%). Never alone.
  * **> 0.96 → close S1**, with a DO-NOT-REPEAT row. Also close S2 unless
    B/A ≤ 0.90 showed near-full byte transfer.
  * If B2 beats B1 by ≥ 2%, carry B2.

### Steps after GO (about 4–5 h CPU, about 1.5 h device)

1. **Flag plumbing** (about 1 h): every site above. CPU gate: the flag is
   absent → bundle-8 command lines, byte-identical.
2. **Kernel** (about 1.5 h): a `ScaleSource` template parameter on
   `p33::dense_lane` (`base/p33_candidates.hpp:76`) and its fused callers.
   For S1b, a loader re-layout under the flag only.
3. **Startup census** (about 0.5 h): one device kernel over all Q6/Q8 dense
   rows, before the first request. Any mismatch is a sticky refusal, with no
   fallback.
4. **CPU gates** (about 1 h): byte fixtures for K = 2560/6144/640/320, split4
   bounds, odd begin (p28 path unchanged), non-finite `d`; a full-shape
   startup dry run (lesson: CPU plans must exercise device startup paths).
5. **Device:** smoke, then a v5 one-load A/B/A/B/A bracket on lane B (12
   prompts, exact vs `iq3-p49-split32-v1`), then lane A; a chain only at
   ≥ +2%.
6. **HC extension** (p60/p73 Q8 `d` per 32): only after step 5 wins.

## 6. Second-metric plan (not started)

**Flag:** `--sequences 1|2`, default 1. Step 0 is a CPU scheduler proof: per
sequence the state banks, KV and token streams equal the single-sequence
oracle, with no speculation or draft. Then a lane-B two-prompt smoke
comparing each sequence's tokens to its single-user stream. Publish only as a
neural.download concurrency profile, with measured points and no projection.

[Note](../../../../notes/2026-10-19-own-runtime-packet177.md) ·
[options.json](options.json) · [price.py](price.py)
