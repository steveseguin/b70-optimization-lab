# Exact two-card within-layer split: sizing from existing evidence (2026-10-28, CPU only)

No GPU, build or service action. `size_within_layer.py` reads the retained profiles and writes `sizing.json`; every
number below is in that file. Paths are relative to `experiments/own-xpu-runtime/research/`.

## Answer

- **Best case: about 1.38× per rank-0 half at g = 5 µs** (10.673 → 7.71 ms), assuming every split halves exactly.
  Calibrated against October 25: **about 1.18× (9.01 ms)**, floor **1.13× (9.48 ms)**. The measured October 25
  layout gave 1.00× (16.72 vs 16.73 ms); projected onto B19 it gives 1.02× at g = 5 and 0.97× at today's 26 µs gather.
- **Break-even g for the head split:** 48 µs (ideal), 29 µs (calibrated), 22 µs (floor). A ≥15% gain needs
  g ≤ 28 / 8.9 / 2.1 µs.
- **Four cards (TP2 inside each pipeline stage) at g = 5:** at most 87 / 77 / 74 tok/s against 66.21 today. Splitting
  only one stage gains nothing, because the other stage stays at 12.4 ms and sets the pace.
- **Prerequisite:** one host thread cannot feed both cards. Launches for both cards plus exchange submits cost about
  10.3 ms, about B19's whole half. Per-card submission threads (about 5.5 ms) or replayed command lists are required
  (`sizing.json` → `host_floor`).

## Data used, and its age

| Role | File | Build and age |
|---|---|---|
| Main: rank-0 per-site profile | `pp4-review-2026-10-28/within-layer-sizing/evidence/b19-rank0-prof-b19-decode-device-profile.jsonl.gz`, copied from `/dev/shm/ownrt-lab-r0-c27prefill/runs/prof-b19/` | The B19 binary itself (`51f32b2655cc`), 2026-10-26 18:53, `OWNRT_DECODE_PROFILE=2`, 46 halves at about 4.1K positions. B24/B25 matched B19 decode (`gdn-prefill-c23/RESULT.md`, `../../../CURRENT.md`). |
| Rank 1 | `decode-next2/profile-final.json` | `d2bc8008eb8d`, 2026-10-26 15:53, about B17. Lacks B19's GDN_PREP (about −0.16 to −0.20 ms on rank 0, `rank0-gdn-c43/RESULT.md`). |
| Calibration | `.../evidence/calib-rank1-prof-a-20261026-decode-device-profile.jsonl.gz`, copied from `/dev/shm/ownrt-lab-20261026/rank1-prof-a/` | 2026-10-26 00:33, about 12 h after the TP runs. Split 23, 1,079 buffers like the TP runs; attention 40.7 µs per site and Q6_K qkv 71.9 µs, the "41–72 µs" quoted for TP step 3. |
| October 25 measurements | `tp/evidence/*summary.json` | Medians of halves 3–16: one card 16.732, replicated 17.083, attention/qkv split 17.042, by slot 16.723, by id (push) 17.023, gather only 17.731 ms. |

One-card halves: rank 0 = 10.673 ms (`rank0-gdn-c43/RESULT.md`), draft = 1.734 ms (`rank0-iq4-c47/results-gdn.json`),
rank 1 = 12.473 ms (`long-context-c43/RESULT.md`). The B19 profile's device span is 10.24 ms; the remaining 0.55 ms of
T1 (gaps between kernels plus host start and finish) counts as replicated.

## Classification of rank-0 sites (B19, µs per half; per-site list in `sizing.json` → `ranks.rank0.sites`)

| Class | µs | Share | Treatment in the head split (H) |
|---|---:|---:|---|
| Routed experts: gate, up, down (all formats) + routed activation | 2452.5 | 23.0% | **Split by slot**; each slot computed whole, combine order unchanged. |
| GDN block: qkv (Q6_K/Q5_K/Q4_K), z, a/b, conv, recurrence, norm-gate | 2175.6 | 20.4% | **Split by head**: 8 key + 24 value heads per card. Conv is per channel; the norm spans head_dim = 128 (`adapter.cpp` `gdn_norm_gate`). |
| Output projection (Q8_0 `attention`, 6144→2560) | 875.4 | 8.2% | **Split by output rows**, 1280 per card, full K. |
| QSA block: qgate, k, v, prepare, attention | 621.1 | 5.8% | **Split by the two KV groups** (12 query heads per card); index heads replicated. |
| Shared expert: gate, up, down, activation | 625.3 | 5.9% | **One unit on one card**; splitting its down projection would split K. |
| HC low/gate GEMVs (attention and FFN blocks) | 1514.2 | 14.2% | Replicated; a row split adds 2 exchanges per HC block. |
| Glue: norms, HC mix/combine/act, router + shared gate, route, gather, combine, status, PLE | 1700.7 | 15.9% | Replicated |
| QSA shared selector: iq, select, append/pool | 160.9 | 1.5% | Replicated (`qsa-kv-head-shard-feasibility.txt`) |
| Gaps + host (T1 − profiled busy) | 547.4 | 5.1% | Replicated |

- **Rank 0:** S = 6124.6 µs (rows, heads or slots) + the 625.3 µs shared unit = 63.2%; R = 3923.1 µs (36.8%).
- **Rank 1:** S = 7837.2 + 693.6 µs (68.4%), including the head's logits and argmax split by vocabulary rows, with one
  extra exchange per half.
- **Nothing is split along K.** The output projection's input gets exchange 1; the MoE combine runs replicated after
  exchange 3; the shared expert's down projection is kept whole.
- **Exchanges:** H has 3 per layer (head outputs, output-projection rows, MoE slots), 69 per rank-0 half. October 25
  slot layout (O1): 1 per layer. October 25 attention + qkv + slot (O2): one per split site plus one per layer, 60 per half.

## Model and calibration

T2 = R + Σ(split-site time on the busier card) + MoE critical card + L·n·g + O_rep.

**The plain model (S/2, no overhead) does not reproduce October 25.** Predicted − measured
(`calibration.naive_model_errors`): replicated −0.35 ms; attention/qkv split at g = 13 µs −0.68 ms; by slot at
g = 26 µs **−1.24 ms**; by id (push) at g = 26 µs −1.07 ms. Two assumptions fail:

1. **Two cards cost something even with nothing split:** O_rep = +0.351 ms (the replicated arm).
2. **Half the slots is not half the time.** The gather alone costs 25.9 µs per layer (gather-only arm). Given that,
   a 5-slot launch took **73.4%** of a 10-slot launch, so the split realises η = 0.531 of the ideal saving: 47% of an
   expert launch's time does not shrink with fewer slots.

**Fitting those two terms** reproduces the slot arm by construction (replay through the projection code: 16.700 vs
16.723 ms). Checks (predicted − measured): by id push −0.05 ms (out of sample); by id pull +0.18 ms (uses 18.15 ms
from the design-doc text); by id pull + attention +0.43 ms (the measured effects were not additive). So the model is
good to about ±0.05 ms on push arms and ±0.2–0.4 ms on pull arms. The dense arm cannot be resolved: it fits exact
halving at g ≈ 23 µs per site (two copies) equally well as η = 0.59 at the closeout's 13 µs.

| Scenario | Experts | Dense and head sites | Overhead |
|---|---|---|---|
| Ideal (the model as asked) | halve exactly | halve exactly | O_rep = 0 |
| Calibrated | η = 0.531 | halve except a 5 µs fixed cost per launch (`decode-next2/RESULT.md`: "about 5–6 µs over the 10.9 µs floor") | O_rep included |
| Floor | η = 0.531 | η = 0.531 | O_rep included |

The MoE uses the best integer slot split with the shared unit on the lighter card (6/4 ideal, 7/3 calibrated). The
asked 5/5 split with the shared expert on one card gives 7.96 / 9.27 / 9.74 ms at g = 5.

## Projections (rank 0, T1 = 10.673 ms; ms and speed-up; `sizing.json` → `ranks.rank0.table`)

| Layout and scenario | g = 3 µs | 5 | 7 | 13 | 26 | Break-even g |
|---|---:|---:|---:|---:|---:|---:|
| O1 Oct-25 slot, calibrated | 10.44 (1.02×) | 10.49 (1.02×) | 10.53 | 10.67 (1.00×) | 10.97 (0.97×) | 13 µs |
| O2 slot + attention + Q6_K qkv, calibrated | 9.89 (1.08×) | 10.01 (1.07×) | 10.13 | 10.49 | 11.27 (0.95×) | 16 µs |
| **H head split, ideal** | 7.57 (1.41×) | **7.71 (1.38×)** | 7.85 | 8.26 (1.29×) | 9.16 (1.17×) | 48 µs |
| **H head split, calibrated** | 8.87 (1.20×) | **9.01 (1.18×)** | 9.15 | 9.56 (1.12×) | 10.46 (1.02×) | 29 µs |
| **H head split, floor** | 9.34 (1.14×) | **9.48 (1.13×)** | 9.62 | 10.03 (1.06×) | 10.93 (0.98×) | 22 µs |
| H2 (output projection replicated, n = 2), calibrated | 9.18 | 9.28 (1.15×) | 9.37 | 9.64 (1.11×) | 10.24 (1.04×) | 35 µs |
| H + HC rows (n = 7), calibrated | 8.62 | 8.94 (1.19×) | 9.27 | 10.23 | 12.32 (0.87×) | 16 µs |

- **Rank 1 under H at g = 5:** 8.65 / 10.07 / 10.82 ms against 12.473; break-even g 55 / 37 / 27 µs.
- **B19's Amdahl ceiling** is 1.45× (g = 0, ideal model).
- **HC row splits pay only at g ≤ 3–5 µs**; at g = 26 they lose 13%.
- **Share of the half that must be splittable for ≥15%** (g = 5, n = 3), from s ≥ 2(1 − 1/1.15 + X/T1)/η:
  33% ideal, 56% calibrated, 70% floor. X = exchanges + O_rep (0.35–0.70 ms); η = realised fraction of S/2
  (0.98 / 0.70 / 0.56). H makes 63% of rank 0 (68% of rank 1) splittable, enough except in the floor scenario.

## Confidence and missing per-site costs

**Medium for the direction, low for the size.** The ideal row is a strict upper bound. The calibrated row rests on one
measured expert efficiency from October 25 kernels; B19's expert kernels have since changed (`decode-next2` packed XXS,
IQ4_NL packed). Never measured:

1. GDN recurrence and QSA attention with half the heads. The calibrated row assumes they shrink like dense GEMVs, but
   a head-shared GDN variant with 1536 instead of 6144 subgroups ran 933 → 1397 µs (`2026-10-25-decode-roofline.md`):
   GDN time depends on parallelism. The floor row covers this case.
2. Five-slot expert launches on B19's kernels.
3. An in-engine exchange near 5 µs. Only microbenchmarks exist (about 7 µs one way with device events); the engine
   gather is 13–26 µs (`2026-10-24-exact-multicard-design.md`).
4. A per-site profile of the pf84–pf91 TP builds; the profiled TP run faulted (`tp/incident-2026-10-25/`).
5. A valid B19 rank-1 profile; the card-43 long-context profiles dropped events (span about 1.04 ms,
   `long-context-c43/RESULT.md`).

**Cheapest next measurements**, each on one card with existing harnesses and no TP build: half-head GDN and QSA kernels
against full ones, and 5-slot against 10-slot B19 expert launches. These pin η. Then, only if the calibrated row
holds, run the peer-store + flag exchange falsifier from `within-layer-parallelism-next.txt` (a).
