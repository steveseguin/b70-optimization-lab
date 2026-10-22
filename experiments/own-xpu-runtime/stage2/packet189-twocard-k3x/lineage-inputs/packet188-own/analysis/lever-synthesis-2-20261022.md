# Two-card lever synthesis 2: the V3 record line (2026-10-22, CPU-only, read-only)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s, cards 0+1.

**Record:** **60.659520 tok/s**, LocalMaxxing `cmvjvabyv040jrf01dricuz8s`. It comes from packet187: bundle 8 + packet153
static snapshot + packet186 V3. The suite is the 128-token capped suite, exact against `iq3-p49-split32-v1`.

Nothing here was built, run on a device, queued or committed. Every price is a per-interval replay of the 1,188 retained
packet187 WS128 intervals through the record metric. The metric is per prompt `99000 / sum(T)`, then the median of
class medians.

**Scripts** (this folder):

* `replay_v3.py` is the replay, decomposition and cross-check against packet186's views.
* `price_v3_levers.py` produces every single-lever price and threshold (`price-v3-output.json`).
* `composites.py` produces the composites, the rank-0 A envelope and the ledger re-prices (`composites-output.json`).
* `collect_dnr.sh` gathers all 258 DO-NOT-REPEAT files into `all-dnr.txt`.

**Labels:**

* **measured** = a retained receipt on this line;
* **transferred** = another identity, lane or micro;
* **assumed** = engineering assumption, with a stated range.

## 0. Answer

**No single open lever prices at +2% on the V3 line.** With V3, rank 1 binds every hit and every miss race, so the
two cards are now nearly balanced:

* Rank 1 is busy for 14.02 ms per hit and rank 0 for 13.09 ms.
* Perfectly equalizing them (the ideal rebalance) is worth only **+2.20%**.
* Any rank-1-only cut saturates at **+2.30%**, at the measured race slack.

| Lever | Price |
|---|---|
| **V3 with layers 24–26 on rank 0 (k=3)**, the largest open single lever | **+1.49% central** (grid +1.40 to +1.55%) |
| k=3 plus ≥ 0.105 ms off rank 0's A | **+2.0%** |
| k=3 plus kernel I/O | +1.88% |
| k=3 plus kernel I/O plus rank-0 prepare moved off A | **+2.39%** |

The next ≥ +2% step is therefore a **composite on top of k=3**. Once k=3 makes rank 0 bind by 0.107 ms, its trims stop
being worthless. Its rank-0 trims are packet147 row-14 items (p137 prepared input / retirement batching), and that row's
own stacking prerequisite (a separate measured ≥ 1.5% two-card gain) is now met by packet186/187.

The only rank-1-only route to +2% is a ≥ 0.349 ms cut of rank 1's half, for example the packet93 packed/transposed
target head (+2.08% at its 100% micro saving). It lost 2.4–2.8% on lane A, the record cards, and is excluded there by
the packet105 and review-15 rows.

## 1. Reproduction and the V3 critical path

`replay_v3.py` reads the 12 × 99 intervals from packet187's
`build/device-cards01-p187-a/WS128/run/repeat-1/*/receipt.json`. It uses packet85's vendored interval model
(`packet186-twocard-v3/v5/interval_model.py`, sha `6627ffa3…`) and adds the boundary command (rank 0, op 15) on the ready
side, exactly as `s186_decision.intervals_v3` does. It reproduces the record **60.65951991975228 tok/s exactly** (diff
0.0). Every per-prompt interval sum equals `token_timestamps[99] − [0]` to 1e-6 ms. `T = max(D, R+C+Bd) + max(B, A+offset) + G`.

| Measured (packet187 WS128) | Hit (932, 78.45%) | Miss (256, 21.55%) |
|---|---:|---:|
| D, rank-1 draft (op 9) | 1.604 | 1.621 |
| Bd, rank-0 boundary, layers 24–25 of the verified token | 1.027 | 1.028 |
| R / C, rank-0 restore / corrected half | 0 / 0 | 0.302 / 11.764 |
| ready = max(D, R+C+Bd) | 1.604 (D binds 100%) | 13.094 (boundary path binds 100%) |
| B, rank-1 half: layers 26–47 + full 248,320-row head | **12.418** | **12.641** |
| A + offset, rank-0 next speculative half | 12.062 | 12.065 |
| G, control gaps | 0.028 | 0.015 |
| **Interval** | **14.050** | **25.750** |

The cross-check against packet186's bracket reproduces both V3 views (60.573 and 60.533) and all three U views. The V3
hit components agree within 0.02 ms.

**Critical-path shares of the record time:**

| Component | Share |
|---|---:|
| Rank-1 B | **75.2%** |
| Rank-0 corrected half C | 15.3% |
| Rank-1 draft D | 7.6% |
| Boundary on misses | 1.3% |
| Restore R | 0.4% |
| Gaps | 0.15% |

Hits take 66.5% of the time and misses 33.5%.

**Rank-0 budget per hit (measured):**

* Draft-window slack D − Bd: **0.577 ms** mean (p5 0.546, min 0.483).
* Race slack B − (A + offset): **0.356 ms** mean (p5 0.246, min 0.116).
* Total rank-0 idle: 0.933 ms.
* On misses, rank 1 idles **11.47 ms** while rank 0 runs R+C+Bd.

**Rank-0 A envelope (measured).** `A − half_completion_ms` = 12.078 − 11.743 = **0.334 ms** per speculative half
(`rank0/timings.jsonl`, 1,524 halves). It contains the host fields `prepare_ms` 0.096 and `p76_retirement_ms` 0.095, plus
about 0.14 ms of capture, upload and dispatch, which is unattributed.

### Thresholds for +2% on the V3 line (replay; compare packet147's bundle-8 rows)

| Cut | Needed | Bundle 8 (packet147) | Note |
|---|---:|---:|---|
| Rank-1 B only (every interval) | **0.349 ms/half** | σ-capped at +0.9% | saturates at **+2.30%** (the race slack); 0.177 → +1.08%, 0.384 → +2.08% |
| Draft D only (hits) | **0.410 ms/hit** | 0.423 | capped by D − Bd (0.577) |
| Correction C only (misses) | 1.524 ms/miss | 1.574 | |
| Same cut on A, B and C | 0.267 ms/half | 0.275 | |
| Free rescue of misses | 13.3% of misses | 14.6% | about 2.86 acceptance points |
| Rank-0 A only | 0 (even 1 ms → 0.0%) | 0 | rank 1 binds |
| Ideal rebalance (equalize per-hit busy time) | ceiling **+2.20%** | | |

## 2. Candidates priced

### (1) V3 with a different split

**Layer types.** The model has 36 GDN + 12 QSA layers, with QSA every 4th layer (`docs/own-runtime.md`). So layers 23
and 27 are QSA and 24–26 are GDN. The V3 boundary is a closed island: "They contain no QSA/position/lookup operator"
(`packet186-twocard-v3/README.md`). Inputs are labelled measured: s1 = 0.463 ms is the rank-1 saving per moved layer;
the rank-0 boundary costs 0.513/layer including its fixed part, against a 0.483 ms layer body.

**Option a: layers 24–26 on rank 0 (k=3).** This lever ranks #1.

* *Mechanism.* Layer 26 (GDN) joins the verified-token boundary. Rank 1 starts at layer 27.
* *Effect.* Bd rises to about 1.54 ms, still inside D (it exceeds D on only 0.6% of hits). B falls by 0.463.
* *Replay:* **+1.49%** (s1 0.43–0.49 × c0 0.483–0.55: **+1.40 to +1.55%**).
  * Hits save 0.345 ms; misses cost +0.067 ms (the boundary is serial after C).
  * After the move, rank 0's A binds 88% of hits, by 0.107 ms on average.
  * +2% needs **≥ 0.105 ms off A**: +1.75% at 0.05, +1.98% at 0.10, +2.13% at 0.15.
* *Build.* Entry TU only, no new kernels:
  * extend the V3 island and `v3_check_plan` to three GDN layers;
  * `rank0_layers 0-26`;
  * loader, census, and the k2/k3 dual-layout switch at request reset (packet186's U/V3 mechanism);
  * memory: rank 0 gains +1.129 GB (half of packet186's measured 2,258,141,716 B for layers 24–25) against 1.97 GB headroom, leaving 0.84 GB.
* *Exactness risk:* low. The kernels are the same; one more never-banked GDN state goes into the proven island.
* *Device:* smoke about 5 min plus a one-load V3/k3/V3/k3/V3 bracket about 8.5 min (packet186's took 486 s): **about 15 min, lane B**.
* *Rows:*
  * packet186 boundary: "Do not run the moved layers inside a speculative half, or before the accept." Respected.
  * packet177 row 2: "Placement / depth / interleave for one sequence | Closed … | A new attribution showing rank0 slack ≥ 1 ms that is outside the draft dependency."
    * Rank-0 slack outside the draft dependency is now 0.356 ms, so speculative moves stay closed by the letter.
    * k=3 uses the draft window, which is what the coordinator's V3 ruling admitted ("V3 uses the draft window (D 1.6 ms) for verified-token work", packet186 DNR).
    * **Needs the same ruling, extended to a third boundary layer.**
  * packet120: "Moving one target layer to rank 0 adds ~0.59 ms to hits … Closed." That was speculative and σ-coupled; not this.

**Option b: layers 23–25 (QSA 23 leaves A for the boundary).**

* Price: **−0.06 to −0.52%**. It shortens A, which does not bind, and lengthens the boundary.
* Build: it would also need QSA KV/position state in the island, which packet186's island forbids.
* **Rejected.**

**Options c and d: k=4 and k=1.**

* k=4 (24–27): impossible (27 is QSA), and −1.21% even if it were GDN, because the boundary overflows D.
* k=1 (25 only): **−2.10%**.
* **k=2 (today) and k=3 are the only viable splits.**

### (2) Rank-1 half levers, now uncapped up to the race slack

**(2a) Target head GEMV on rank 1.** The head is 248,320 rows × 3,380 B ≈ 839 MB/token. That is bandwidth-bound: about
1.40 ms (older anchor 1.403684 ms; packet93 micro 1.417 ms).

* **packet93 head-transpose** (block-transposed packed Q6_K head):
  * microbench 1.417 → 1.033 ms (−0.384);
  * engine transfer on lane B in the un-split era 0.177 ms (+0.86%) (`notes/2026-10-18-own-runtime-first-lane-results-p91-p93.md`).
* On V3: **+1.08%** at the measured transfer, **+2.08%** at 100% of the micro.
* *Rows:*
  * Review 15: "Packet93's head-transpose is excluded: its completed A candidate is 53.906391 tok/s, between controls of 54.959464 and 55.469037, 2.8171% below the stronger control."
  * packet93x: "head-transpose 2.369% slower on A … A follow-up needs head and shared/separate draft-prefix timings on cards 1 and 3, then fresh matched engine repeats."
  * packet105/105b: "A lane-B head result never qualifies lane A (packet93)."
  * The record runs on lane A (the head is on card 1). **Closed for lane A until that card-1 timing exists.**
* Other head formats are closed:
  * packet74 packed Q6/Q8 dense + head: "measured −0.8 / −2.4 / −2.9%";
  * packet183 S1/S2: "Closed: loss -6.2% … S2 … is closed with it";
  * packet161 early argmax: "mean required reads 99.999919%".
* Build: load-time head layout, so fresh loads are needed (a one-load head switch is refused, packet185). Lane-A
  C/X/C/X/C is about 25 min, plus a card-1/card-3 head micro of about 10 min.
* Exactness: none (reversible bytes, unchanged order).

**(2b) Draft D (1.60 ms on rank 1, 7.6% of the critical path).**

* What packet158 closed, and at which numbers: kernel time ≈ 1.38 ms; positive gaps routed experts 0.163, input/embedding
  0.110, attention 0.088, projections 0.041, norm 0.030, argmax 0.026, shared expert 0.024; **sum ≈ 0.48 ms**. "100%
  closure gives ≈ +2.3% and the lab's 20% transfer rule gives ≈ +0.45%"; "the most host batching could add is ≈ +0.9%".
  Revisit: "a new mechanism that removes a measured ≥ 0.42 ms/hit from the draft's critical path".
* On V3 the threshold is 0.410 ms/hit.

| Draft cut on V3 | Price |
|---|---:|
| 100% of the gaps | **+2.35%** |
| 20% | **+0.46%** |
| Host-batching ceiling, 0.19 ms | +0.92% |

* **packet156:** "Existing post-prefix suffix slack supports only 0.29–0.32%; closed before build."

**(2c) Draft head (80,128 rows + argmax, 0.472 ms, packet158 replay) moved to rank 0.**

* Rank 1 runs the trunk and starts B 0.47 ms earlier. Rank 0 runs the head after the boundary and the trunk-hidden import.
* Price: **+1.31%** (+1.07 to +1.34% over transfer 0.05–0.10 ms and head 0.40–0.52 ms). Rank 0's A then binds.
* With k=3 it is **−0.97%**: both levers spend the same rank-0 window.
* packet160 priced the *free* donation ("Full head+argmax donation is 0.471703 ms/hit, +2.235%"); on V3, free would be +2.31%. It is not free.
* *Rows:*
  * packet79 (via packet158): "Draft stays rank1; no head duplication, rank relocation or topology workaround";
  * packet106b: "Draft-prefix split lost … No draft suffix dispatch, split protocol or extra mailbox".
* **Closed family**, and in any case below the k=3 price.

**(2d) Rank-1 merge and receipt path.** V3 has no merge; the un-split head removed the p105 suffix round trips. What is
left is synchronous round trips: D 2, B 3, Bd 1, A 1, C 2.

* Each is a measured 22.7–25.5 µs (packet165 two-card `p105-transfers.jsonl`); the kernel store/stamp at 5 µs is assumed.
* Kernel-I/O port price: **+0.57%** (generous +0.95%). Under k=3 it adds +0.39 points, because rank 0's round trips start to count.
* packet177 row 3: "Nothing to port … All copy stalls are < 0.1 ms/token (+0.6% if removed). | Two-card fills or a BCS queue are introduced."
* The price agrees. **Closed by the letter**; worth keeping as a stacking component.

### (3) The miss path (25.75 ms, 21.55% of intervals, 33.5% of time)

R is 0.302 (static already removed 0.25 of it; it was 0.55), C is 11.764, the boundary 1.028, and B 12.641. Rank 1 idles
11.47 ms per miss.

| Miss lever | V3 price | Ledger row (quoted) |
|---|---:|---|
| Remove all restore R (upper bound) | +0.39% | packet144: "Layer-local restore overlapped with C | All-R upper counterfactual +0.691% … Do not reopen packet121 for a small copy gain." |
| Rank-1 B warm after idle (miss B 12.641 vs hit B 12.418, measured 0.223) | +0.29% | packet144: "Rank1 weight warming during correction | B-only impossible-removal counterfactual is +0.916% … packet119/138 negatives remain." |
| Free rescue of the 20/256 out-of-prefix misses | +1.17% | packet144: "Only 20/256 record misses have actual IDs outside 80,128 … +1.233% … Do not retune packet114 N." |
| Boundary free on misses (impossible: Bd needs C's layer 23) | +1.35% | packet144: "Corrected layer-granular handoff | Layer24 requires layer23 streams." |
| Fuse C and Bd into one command (−0.02 ms, assumed) | +0.03% | none |
| Correction cooperation / mirrored layers | — | packet148: "row coop +1.04/+1.32% … whole attention-head cooperation +1.569/+1.914% … Layer23 requires 1,128,881,622 bytes … versus 786,269,478 margin." Rank 1 now has 0.63 GB headroom; a slim layout frees 2.26 GB (two layers, not 24). |

**Nothing open reaches +2%.** The C-only bar is 1.524 ms/miss, about 13% of the corrected half, and only symmetric
kernel work could supply it. That work is closed: packet175b D1 "B/A 1.0665"; packet183 S1 "−6.2%".

### (4) Static snapshot

Static is already in packet187 (`snapshot_host=static`). There is no further gain to price.

In packet186's load, A fell 0.41 ms and R fell 0.25 ms from the U views to the V3 views. Those views changed both
`boundary` and `snapshot_host` together. A runs the same layers 0–23 in both, so the fall is consistent with static, but
it is not isolated.

The residual 0.334 ms A envelope matters only after k=3 (section 2.1).

### (5) Items packet147/177 deferred on "rank 1 binds" or similar

None is literally worded "when rank 1 binds". These are the conditional rows that move with V3:

* **packet147 row 14 (p137 exact input precomputation / prepared-buffer reuse / event-retirement batching).**
  * Row text: "p137 two-card projection +0.26–0.62% … p137 stays closed-deferred until a separate measured ≥1.5% two-card gain."
  * **The condition is now met.** packet186 measured +3.31% and packet187 +3.17%.
  * V3 price on rank 1's D: **+0.21% to +0.53%** (D −0.044 to −0.110/hit; the 0.110 is packet158's input/embedding gap).
  * On rank 0 it is worth something only under k=3: k=3 + kernel I/O + p137 is **+2.06%**; k=3 + kernel I/O + rank-0 prepare (0.096) off A is **+2.39%**.
  * Build: packet137 already has the exact 1,271,398,400-byte draft-embedding table (`table.json`, GNU = Intel) and the target-decode hoist, on the bundle-7 line. It needs an entry-TU port to V3. Host-pinned table: no device memory.
* **packet177 row 2 (placement):** see 2.1 option a. Not met for speculative moves (0.356 ms < 1 ms); boundary moves need the V3 ruling.
* **packet177 row 3 (kernel I/O):** not met (no fills or BCS). Price +0.57%.
* **packet147 sensitivities and packet160 head donation:** re-derived above (section 1 table; 2c).

## 3. Ranked table (top 5, single levers on the V3 line)

| # | Lever | Mechanism | Build | Exactness risk | Device | Priced gain (replay) | Ledger status |
|---|---|---|---|---|---|---|---|
| **1** | **V3 k=3: layers 24–26 on rank 0** | GDN layer 26 joins the verified-token boundary in rank 0's draft window; rank 1 starts at 27 | entry TU, island and loader, census (+1.13 GB rank 0) | low | about 15 min lane B | **+1.49%** (+1.40…+1.55); **+2.0% with ≥ 0.105 ms off rank-0 A**; +2.39% with kernel I/O + prepare off A | V3 family; needs the V3 ruling extended (packet177 row 2) |
| 2 | Draft head → rank 0 | trunk on rank 1, 80,128-row head + argmax on rank 0 | entry TU + loader + 2 messages | low | about 15 min | +1.31% (+1.07…+1.34); −0.97% combined with #1 | closed: packet79/106b/160 |
| 3 | Out-of-prefix miss rescue | complete omitted draft rows only on miss-conditioned paths | kernels + controller | medium | about 20 min | ≤ +1.17% (free upper bound) | closed: packet144 |
| 4 | Head-transpose (packet93) on rank 1's un-split head | packed, block-transposed Q6_K target head (−38% bytes) | existing kernels, load-time layout | none | lane A: about 35 min | +1.08% measured transfer; +2.08% at the 100% micro | closed for lane A (review 15, packet105) |
| 5 | Kernel foreground I/O, two-card port | kernel loads/stores + stamp replace synchronous round trips | entry TU + small kernels | none | about 15 min | +0.57% (≤ +0.95%); +0.39 points on top of #1 | closed: packet177 row 3 |

Stacking-only components, not ranked:

* **p137** at +0.21–0.53%; packet147 row 14's prerequisite is now met.
* Draft-gap closure at 20%: +0.46%.

## 4. Recommendation

**Build V3 k=3 (layers 24–26 on rank 0) as the base of the next composite, together with the p137-family rank-0
trims.** Measure it in one lane-B load.

1. **Content.**
   * k=3: entry TU only, using packet186's V3 machinery extended by one GDN layer.
   * Rank-0 kernel-I/O round trips: export/import legs.
   * Rank-0 prepared-input reuse, so `prepare_ms` (0.096) leaves A's span.
2. **Views.** V3(k2) / k3+trims / V3 / k3+trims / V3, plus p150-style rank-0 scope attribution of A's 0.334 ms envelope.
   This measures the trim instead of assuming it.
3. **Price.** k3 alone is +1.49%. k3 + kernel I/O is +1.88%. k3 + kernel I/O + prepare off A is **+2.39%**. At least
   0.105 ms of rank-0 trim is required for +2%.
4. **Kill rules.**
   * Stop if the measured k3 hit saving is < 0.25 ms.
   * Stop if the boundary exceeds D on > 5% of hits.
   * Stop if the trims remove < 0.105 ms of A.
   * Chain only at ≥ +2% over the in-load V3 views and ≥ 1.02 × 60.659520.
5. **Ruling needed.** packet177 row 2 is satisfied for V3 by ruling, not by its letter, so the coordinator must extend
   that ruling to a third verified-boundary layer.
6. **Cost.**
   * CPU: about 6–8 h. This is extending V3's island proof, CPU miniature and production-shape census, plus porting
     p137's input path.
   * Device: about 15 min, then a 47 min chain if it qualifies.

**Why not the others.**

* #2 and #4 are closed families. #4 also has a measured lane-A loss on the record cards.
* #3 is a free-cost upper bound below the bar.
* #5 is a component, not a lever.
* The rank-1 route (B cut ≥ 0.349 ms) exists only through the packet93 head on lane A. The cheapest way to unblock it is
  packet93x's own revisit: card-1 vs card-3 head micro timings, about 10 min.

## 5. Rejected, with closing rows

| Lever | V3 price | Closing row |
|---|---:|---|
| Split 23–25 | −0.06…−0.52% | packet186 README island: "no QSA/position/lookup operator"; A does not bind |
| Split 24–27 / k=4 | −1.21% and illegal (27 is QSA) | as above |
| Split 25 only (k=1) | −2.10% | measured V3 k=2 is better |
| Speculative layer moves (p120 style) | loss | packet120 "Moving one target layer to rank 0 adds ~0.59 ms to hits … Closed"; packet186 "Do not run the moved layers inside a speculative half" |
| Re-split the target head (suffix to rank 0) | loss (A + σ = 12.54 > B) | packet185 "Un-split ALONE is a loss"; σ coupling (packet128b) |
| Draft on rank 0 (whole) | loss | packet79 "−2.3% / −1.3% on lane A … draft depends on rank-1 final state … do not repeat" |
| Perfect 2× draft split | loss on V3 (rank 0's window holds the boundary) | packet160 "Ideal +3.308% leaves 62.44 µs total overhead" (bundle 8) |
| Draft kernels / host batching | +0.46% (20%), ≤ +0.92% | packet158 draft-line closure; packet156 "≈ 0.3%" |
| Packed / metadata head and dense formats | loss | packet74 "−0.8 / −2.4 / −2.9%"; packet183 "−6.2% … S2 … closed with it"; packet175b "B/A 1.0665" |
| Early target argmax | — | packet161 "mean required reads 99.999919%" |
| Restore / warming / out-of-prefix / layer handoff (miss path) | +0.29…+1.17% | packet144 rows quoted in §2(3) |
| Correction cooperation / layer mirrors | memory-infeasible | packet148 rows quoted in §2(3) |
| Sibling / second candidate | — | packet96 "held-out gain 0%"; packet132 "+1.77%" failed gate |
| Intra-layer TP | — | packet177 row 1 "At the measured 18.6 µs it is −15.6%" |
| Prompt lookup / n-gram | — | packet146 policy-closed |
| Two-sequence aggregate | — | packet177 row 4 "Forbidden" |
| Static snapshot | already in the record | packet153 "could join a future composite bundle" (done in packet187) |
