# Two-card lever synthesis, 2026-10-22 (CPU-only, read-only)

> Copied into packet185 (`analysis/`) on the coordinator's ruling: packet177(b) stays closed by its letter until the
> attribution is MEASURED; packet185 is that measurement. Content unchanged except this note and the scripts line.

Line: Qwen3.8 Flash-Next UD-IQ3_XXS (the quantized compressed version), own Xe runtime, two B70s.
Record: **58.798109 tok/s**, packet136 bundle 8, 128-token capped suite, exact vs `iq3-p49-split32-v1`.
Nothing here was built, run on a device, queued or committed. Every price is a replay of the
1,188 retained record intervals (`stage2/packet160-critical-path/evidence/record-intervals.csv`)
through the record metric (prompt rate 99000/sum(T), median of class medians). The replay
reproduces 58.798108759 exactly and reproduces the ledger's own +2% thresholds
(D-only 0.4231 ms/hit, symmetric 0.2752 ms/half, as in packet147).

Scripts (this folder, tracked in packet185 `analysis/`; run from the repository root): `price_levers.py` (replay + all levers, writes `price-output.json`),
`v3_corners.py` (corners, kill thresholds), `p120_components.py` (p85 interval split of retained
v4 receipts). Labels: **measured** = retained receipt on this line; **transferred** = receipt from
another identity; **assumed** = engineering assumption.

## 0. Answer in one paragraph

No body-kernel, draft, miss-path or copy-path lever on the ledger prices at +2%, and the two-card
port of the one-card kernel-I/O win prices at **+0.5% to +0.7%** (never measured on two cards).
The only lever that prices at +2% or more is structural: **un-split the target head and run rank 1's
first two body layers (24, 25) on rank 0 for the verified token, in rank 0's draft-wait window**
("verified-boundary rebalance", V3). Central **+3.1%** (grid +2.6% to +4.2%, pessimistic corners
+2.2%). It works because of a coupling the ledger has described but never priced: with the split
head, rank 1's emission waits for rank 0's speculative half plus a fixed suffix service
**σ = 0.478 ms (measured in six coupled arms)**. On bundle 8 rank 1 is only 0.126 ms above that floor,
so every rank-1-only saving is capped at **+0.9%**, and every past rank-1→rank-0 move lost because it
lengthened A + σ. V3 sits in the placement family that packet177 closed; by the letter of its revisit
condition it is **not** reopened (the retained receipts give 0.80 ms, not ≥ 1 ms, of new rank-0 slack
outside the draft window). It needs an explicit coordinator ruling, or a one-load measurement. Without
that ruling, the honest answer is: **no open two-card lever prices at +2% today.**

## 1. The structural fact the ranking rests on: the split-head coupling σ

The p85 interval split of retained v4/v5 receipts (`p120_components.py`), hit means in ms:

| Arm (source) | Line | A | B | B − A | Reading |
|---|---|---:|---:|---:|---|
| p106b production (un-split head) | bundle-6 era | 13.145 | 13.677 | 0.533 | B = rank 1's own work |
| p106b head split | bundle-6 era | 13.145 | 13.625 | **0.480** | coupled |
| p120 production | bundle 7 | 12.799 | 13.277 | **0.478** | coupled |
| p120 25/23 (rank 1 lost a layer) | bundle 7 | 13.387 | 13.870 | **0.483** | coupled: B *rose* 0.59 with A |
| p127 production | bundle 7 | 12.816 | 13.295 | **0.480** | coupled |
| p127 81,920 suffix rows | bundle 7 | 12.937 | 13.625 | 0.687 | coupled, σ +0.207 for +35,840 rows |
| p131b controls (×2) | bundle 7 | 12.81 | 13.28–13.29 | **0.477–0.478** | coupled |
| p131b banks (= bundle 8) (×2) | bundle 8 | 12.48–12.49 | 13.12–13.13 | 0.63–0.65 | A fell 0.32, B only 0.16: decoupled |
| record, packet160 (1,188 intervals) | bundle 8 | 12.482 | 13.086 | 0.604 (p10 0.543) | rank 1 binds, margin 0.126 |

Paths: `stage2/screen/v4-lanes/evidence/{p106b-13e3630d590c-B-grid-*,p120-B-grid-*,p127-B-grid-*,p131b-e5cfcb55493f-B-*}/run`.

Mechanism (source, `base/p105_runtime.hpp` `service`/`merge_target`; packet128b finding): rank 0
services the 46,080-row suffix only after its speculative half drains on the single in-order CCS,
then 4–5 synchronous copies; rank 1 merges after one more export/upload. So

`emission = max(rank1_own, A + σ)`, σ(46,080 rows) = **0.478 ms**, slope 5.78 µs per 1,000 rows
(p127), so about **0.21 ms of σ is fixed round-trip overhead** (measured 22.7–25.5 µs per synchronous
copy, `stage2/packet165-warm-prefill/two-card/evidence/requal-tp2-a-20261020/run/ranks/rank*/p105-transfers.jsonl`,
6,495 samples per leg).

Consequences, from the replay:

* Rank-1-only savings saturate at **+0.9%** (0.1 ms → +0.55%, 0.2 → +0.81%, ≥ 0.5 → +0.905%).
  packet160/173 priced the same B-only cut without σ (0.333 ms → +2.0%, saturating at +3.85%);
  those sensitivities overstate every rank-1-only lever.
* A-only or rank-0-only savings give 0 until rank 1 is cut too (packet160 already says so).
* Moving work to rank 0 lengthens A + σ, which is why p120, p127 and p130 lost (packet128b said this
  qualitatively: "rank 1 waits for rank 0's head-suffix rows ... explains why moving more rows/layers
  to rank 0 lost (packets 127, 120)").
* Bundle 8 is balanced within 0.126 ms, so a symmetric cut must clear 0.2752 ms per half on both
  ranks for +2%. Every symmetric kernel lever on the ledger is closed below that (section 4).

## 2. Ranked table (top 5)

Gains are pooled replay gains on the record metric. They are planning numbers, not speeds.

| # | Lever | Mechanism (one sentence) | Paths touched | Priced gain (replay) | Build | Exactness risk | Device per screen row | DNR status |
|---|---|---|---|---|---|---|---|---|
| **1** | **V3 verified-boundary rebalance** (un-split head + layers 24–25 on rank 0, non-speculative) | Put the full 248,320-row head back on rank 1 so emission no longer waits for A + σ, then let rank 0 run layers 24–25 for the *verified* token in its idle draft-wait window and hand rank 1 the layer-25 streams. | rank 0 (new boundary command, 2 GDN layers + their non-banked state), rank 1 (starts at layer 26, full head, no merge), handover (layer-25 streams instead of layer-23), controller; draft unchanged | **+3.1% central**; grid +2.6 to +4.2%; corners +2.2%; **+0.64% if the 0.743 ms accept stays serialized ahead of the boundary**, +2.2% with p153 static snapshot | No new kernels. Loader/placement for 2 layers on rank 0, a rank-0 "boundary" command, controller reorder, target_head=production (existing selection), v5 dual-placement switch. Size L (~0.8–1.5k lines), ~6–10 h CPU | Arithmetic: none (same kernels per layer; p120 placement and the pre-p105 head were exact). State: medium (layers 24–25 state on rank 0 must see only verified tokens across hit/miss/no-guess/EOS/prefill/reset) | smoke 12×64 ~5 min + one-load C/U/X/C/X/C 12×128 ~12 min ≈ **20 min lane B** (rank 0 +2.3 of 4.07 GB headroom, rank 1 +0.16 of 0.786 GB) | **Borderline: packet177(b) family.** See 3.1 |
| 2 | Two-card kernel foreground I/O (packet176 port, plus device-resident suffix service) | Replace each synchronous queue memcpy+wait (draft prologue, merge export/upload, tail readback, suffix import/export) with compute-kernel loads/stores to pinned memory plus a stamp spin, so no copy can be offloaded to a BCS. | rank 1 D prologue and merge, tail; rank 0 suffix service and C prep; handover | **+0.53%** central (2 D, 3 B, 4 σ, 2 C round trips at 23→5 µs); +0.68% with 5 async engine switches at 5 µs; ≤ +1.17% generous | Entry TU + small kernels (TailStore/HeadLoad analogues); M | Low (no arithmetic change; packet176 pattern) | ~15 min (smoke + v5) | Closed on CPU by packet177 row 3; price agrees (+0.6%). Never measured on two cards |
| 3 | Draft head to rank 0 (trunk stays on rank 1) | Rank 1 exports the draft-trunk hidden; rank 0 (the guess consumer) runs the 80,128-row draft head, so rank 1 starts B 0.47 ms earlier. | rank 1 D, rank 0 head; handover | +0.37% with split head (σ binds); **+1.02%** with un-split | Entry + loader; M | Low | ~15 min | Closed family: packet160 a1, packet106b draft split, packet158 draft-line closure |
| 4 | V1 un-split + speculative 25/23 (layer 24 inside A) | Same decoupling, but layer 24 runs speculatively inside A (p120 placement). | rank 0 A/C, rank 1 B, head | **+0.74%** central (k=1; range +0.4 to +1.3%); k=2 **−0.74%** (A tail blocks rollback on misses) | Reseal-level if bundle 8 accepts split25 + target_head=production, else entry TU; S/M | None | v4 grid 3 arms ~20 min | Closed family: packet120 (−3.9%), packet148 "do not silently change static hit placement" |
| 5 | packet153 static snapshot descriptors | Precompute snapshot descriptor tables at load. | rank 0 accept/capture | **+0.35% measured** (exact, v5, drift 0.057%) | Built and sealed | None (measured exact) | already measured | Sub-bar by its own result; explicitly "could join a future composite bundle". Makes V3 robust to accept ordering (+0.64% → +2.2%) |

Below +2% and listed for completeness: V3 with one layer (+0.94% central, +0.5 to +1.7%), V3 with
three layers (+0.9%, rank 0 saturates), un-split alone (−1.2% at u = 0.2), head rows to rank 0 inside
the split (+0.28% at about 11,000 rows; 35,840 rows −0.33% in the model, −1.95% measured by p127).

## 3. Lever 1 in detail (V3)

### 3.1 Ledger rows checked (quoted)

* **packet177 DO-NOT-REPEAT, row 2:** "Placement / depth / interleave for one sequence | Closed. The
  ceiling from rank0's 1.23 ms draft wait is +2.9%, and every measured move lost (p120, p127, p79,
  p71c). | A new attribution showing rank0 slack ≥ 1 ms that is outside the draft dependency."
  * *Reading.* V3 is in this family. The new attribution is section 1: all four losses happened in the
    coupled regime, and p177's +2.9% ceiling ignored σ. After un-splitting, rank 0's deadline moves
    from the emission to the next handover. The new rank-0 slack outside the draft window is
    B + u − A = 13.086 + 0.20 − 12.482 = **0.80 ms**: below the 1 ms of the letter. The draft window
    itself (1.23–1.6 ms) is filled with draft-independent work (verified-token layers).
  * *Ruling needed.* Treat the condition as met in intent (new σ attribution, no re-counted slack), or
    obtain a measured un-split view first (the U view of the bracket below, or a reseal-only v4 arm).
* **packet148:** "correction-only moving layer boundary | ... Moving serial layers does not remove C ...
  | ... Do not silently change static hit placement or revive packet120/123."
  * V3 changes hit placement openly and is neither p120 (a speculative layer inside A, with the suffix
    coupled) nor p123 (a partial layer in A's tail).
  * Memory: two GDN layers, about 1.13 GB each by p148's layer-23 census, go to rank 0, which has
    4.07 GB of headroom (packet177). Rank 1 *frees* memory.
* **packet120 result note:** "Moving one target layer to rank 0 adds ~0.59 ms to hits and ~1.0 ms to
  misses ... Closed."
  * Explained by σ: A grew 0.59 and B tracked it (0.483).
  * The measured 0.59 ms per-layer cost on rank 0 is carried as the pessimistic c0.
* **packet127 note:** "rank-1 → rank-0 work moves are closed until the in-engine attribution (packet 128)
  shows otherwise."
  * packet128b is that attribution. It names the suffix wait as the cause.
  * V3 moves head rows the *other* way (all of them to rank 1).
* **packet130 note:** suffix interleave −1.61%, closed. V3 removes the suffix instead of reordering it.
* **packet160 DO-NOT-REPEAT:** "Rank0 draft-wait idle time can serve B-layer experts for free | During B
  it executes A/suffix; ... 1.889% before exchange."
  * V3 serves no B work during B and exchanges nothing per layer.
  * It runs whole layers before B, with one hidden handoff, the same one as today.
* **packet156:** "Do not equate rank0's 1.227 ms draft overlap with rank1 suffix idle time." Respected:
  the window is used for rank-0 work.
* **packet123:** "Do not call bundle7's 0.482640 ms command tail usable rank0 slack. The split-head suffix
  executes outside the rank trace, and rank1 waits for it." Consistent: that 0.4826 ms *is* σ. V3 does
  not use it.
* **packet79:** "MTP draft on rank 0 ... -2.3% / -1.3% ... do not repeat." The draft stays on rank 1.

### 3.2 Pricing model and inputs

Per interval, using the record's own D, A, B, R, C, G:

* own'' = B + u − k·s1, with k = 2.
* tail = max(0, A − own''): the previous speculative A is still running at emission.
* Hit: T = max(D, tail + k·c0 + export + capture) + own'' + G, floored at rank 0's cycle
  k·c0 + A + capture + export.
* Miss: T = tail + R + C + k·c0 + export + own''_miss + G.

| Input | Value | Label / source |
|---|---|---|
| u, extra rank-1 time for the 46,080 rows minus removed merge round trips | 0.20 (grid 0.15–0.25; bound ≥ 0.052) | Rows: transferred (draft-head roofline 0.445348 ms / 80,128 rows, packet158). Bound: measured (p106b production vs split B). Round trips: measured |
| s1, rank-1 saving per GDN layer | 0.48 (0.45–0.55) | Derived from measured B minus head (p128b 1.17) over 24 layers; GDN vs QSA split from packet110 (transferred) |
| c0, rank-0 cost per layer | 0.55 (0.49–0.62) | 0.59 measured in p120, which includes speculative snapshot growth; V3's layers are non-speculative |
| export / capture GPU | 0.025 / 0.08 | Export measured (23 µs legs); capture assumed (p131b rotates banks; about 19 MB of flat copies) |

Results:

| Case | Gain |
|---|---|
| Central | **+3.08%** (hits about 14.70 → 13.94 ms) |
| u at the lower bound 0.05 | +3.86% |
| Pessimistic: u 0.26, s1 0.45, c0 0.62 | +2.23% |
| Pessimistic plus 0.05 ms extra round trip | +2.16% |
| Central, accept fully serialized | +0.64% |
| Central, p150's removable 0.335 ms serialized plus 0.05 round trip | +2.28% |

**Kill thresholds** (central falls to +2%):

* u > 0.39 ms;
* c0 > 0.73 ms;
* s1 < 0.39 ms;
* any serialized accept > 0.46 ms;
* extra rank-0 round trip > 0.36 ms.

D-window fit: the boundary ends at tail + 1.1 + 0.105 ≈ 1.36 ms against D = 1.597, a 0.24 ms margin.

### 3.3 Build requirements

1. The bundle-8 copy loads layers 24–25 (GDN) on rank 0 with non-banked state.
2. A new rank-0 command `boundary(token, position)` issues the two layers asynchronously and exports the
   layer-25 streams (20 KB) when done.
3. Controller (`native_controller.hpp`) order:
   * On a hit: `wait(0)` → `start(0, boundary)` → `call(0, accept)`, so the accept host work overlaps the
     boundary GPU work. Include p153 static descriptors so the ordering is not load-bearing.
   * On a miss: `rollback` → corrected half → `accept` → `boundary`.
   * The prompt and no-guess paths also run the boundary.
4. Rank 1 starts B at layer 26 and selects `target_head=production` (full head, no p105 merge).
5. v5 dual placement: rank 0 holds layers 24–25 and rank 1 keeps its copies, switched at request reset.
   * Views: C0/U1/X2/C3/X4/C5, where U is un-split only, a diagnostic that measures u and the decoupled
     B − A.
6. CPU gates before the device:
   * full-shape startup on both ranks;
   * IPC miniature with token, draft-proposal and state parity across hit, miss, no-guess and EOS;
   * request-reset byte checks;
   * real memory census.
7. Screen gate: both X views ≥ +0.5% over every warm control, drift ≤ 1%, 60/60 exact, identical draft
   proposals. A chain only at ≥ +2%.

## 4. Considered and rejected (closing rows)

| Lever | Closing row (quoted or summarised with path) |
|---|---|
| S1 metadata dense scales; S2 planar 6-bit | packet183: "**Closed: loss -6.2%** ... **S2 ... is closed with it** ... measured B/A = 0.938." |
| D1 scale-word multicast | packet175b: "weighted dense GEMV B/A 1.0665 > 0.97". |
| D2 dense L2 warm-ahead | packet175: "B/A 1.4386 > 0.97". |
| Packed Q6/Q8 dense + head | packet74, via packet177 §3: "measured −0.8 / −2.4 / −2.9%, exact; the in-register 6-bit unpack costs more". |
| Intra-layer TP | packet177 row 1: "Closed on CPU ... Break-even is 6.62 µs per phase ... At the measured 18.6 µs it is −15.6%." |
| 25/23, head rows, suffix interleave, draft on rank 0, depth 2 | p120 −3.9%, p127 −1.95%, p130 −1.61%, p79 −2.3/−1.3%, p71c −46.8% (packet177 §3; notes 2026-10-18). |
| Draft kernels / host batching / suffix slack | packet158 closure: "sum of all positive gaps is ≈ 0.48 ms ... ≈ +2.3% at 100% ... most host batching could add is ≈ +0.9%"; packet156 "≈ 0.3%". |
| Miss-path: cooperation, restore, early loser, omitted draft rows | packet144 / packet148 rows (all < 2%; free rescue of out-of-prefix misses +1.233%). |
| Sibling / second candidate | packet132 "+1.77%"; packet96 "held-out gain 0%". |
| Shared correction graph | packet160 d3 / packet149: "+7.69 ms/miss transport". |
| Early target argmax | packet161: "mean required reads 99.999919%". |
| Router / route fusion, pruned top-10 | packet164 ("visible gaps 0.003 ms/half"); packet112. |
| IQ2 expert decoders | packet162b: "4.79–4.83× slower"; packet173 prior E1n2 +0.22%; p95/p99/p102/p104/p115/p119 rows. |
| N3 RMS partials, G1 gated norm | packet173 priors +0.28% / +0.24%; packet140 row ("+1.305% at 20% transfer" for all scale sharing). |
| Class layout / order600 | packet142 null (58.585/58.620 vs 58.624–58.636); packet145 null (packet147 note). |
| Exact token-input table | packet147 row 14: "p137 two-card projection +0.26–0.62% ... closed-deferred". |
| Prompt lookup / n-gram | packet146: policy-closed. |
| Resident lookup copies | packet167: "packet136 WS/WSs/WS128x/WS128 each record zero major faults". |
| Fill pacing | One-card only, packet182 row (≤ +1.42% ceiling). Two cards have no fills (packet177 e1). |
| Two-sequence aggregate | packet177 row 4: "Forbidden ... neural.download concurrency profile only." |
| Any rank-1-only kernel/format cut (head format, rank-1 copy removal, ...) | Not closed by a row, but capped at **+0.9%** by σ (section 1). |

## 5. The kernel-I/O question asked by the coordinator

* **Has packet176/182 kernel foreground I/O ever been measured on two cards?** No.
  * Every packet176/182/foreground-io mention is in one-card packets, the SCOREBOARD header,
    `docs/own-runtime.md` or the results README.
  * The two-card analogue was audited only on CPU by packet177 e1: "Nothing to port ... every copy is
    on the in-order CCS queue ... +0.6% if removed".
  * The *reason* is weaker than the *magnitude*. packet171b/176 showed that "a memcpy on any queue can
    still be carried by a copy engine (UR copy offload)". The two-card engine issues all copies as
    `queue_->memcpy` on an in-order queue (`base/single_device.cpp:84,101`), with no
    `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD`.
* **Why the one-card +3.9% does not transfer.**
  * 1.095 of the 1.168 ms/token it removed was fill-coupled transfer: foreground and maintenance lists
    shared one copy engine.
  * Two cards have no fills. What remains is the fixed round-trip cost, measured on two cards at
    22.7–25.5 µs per synchronous copy.
  * On rank 1's hit path that is about 5 round trips (draft `merge.hidden` copy + drain, embedding
    upload, prefix-export, index upload, tail readback). On rank 0's σ it is about 4–5.
* **Replay price.** +0.53% central, +0.68% if 5 asynchronous engine switches cost 5 µs each, at most
  +1.17% generous. Below the bar.
* **Value inside a bundle.** Inside V3 it adds little, because V3 already removes the merge and suffix
  round trips.

## 6. Recommendation

**Recommend V3**, with an explicit coordinator ruling on packet177(b). Run it as one load on lane B
(views C/U/X/C/X/C, about 20 minutes of device time) after an L-size CPU build. Include p153 static
snapshot descriptors so the accept ordering is not load-bearing.

* **Why it ranks first.** It is the only lever whose replay clears +2% across every parameter corner
  (+2.2% to +3.9%, central +3.1%). It reuses existing kernels and the existing un-split head path, so
  arithmetic risk is nil. Its premise (σ) is measured in six arms, not assumed.
* **Kill rule.** If the U view shows u > 0.39 ms, or a decoupled B − A below about 0.6 ms, stop before
  any record chain.
* **Why the others rank lower.**
  * Kernel I/O (#2): +0.5–0.7%; the one-card mechanism, fill coupling, is absent.
  * Draft head to rank 0 (#3): ≤ +1.0% and inside the closed draft-split family.
  * V1 (#4): +0.74%, or a loss at k=2, because the speculative A tail blocks rollback on misses. It is a
    p120 relabel.
  * p153 (#5): measured +0.35%; useful only as a V3 companion.
* **If the ruling is "closed by the letter".** No open two-card lever prices at +2%. The next useful work
  is then the U-view measurement alone: a reseal of bundle 8 with `target_head=production`, about
  20 minutes on a v4 grid. It supplies the slack attribution packet177 asks for.
