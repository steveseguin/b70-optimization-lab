# Two-card lever synthesis 4: after the k3x record (2026-10-22, CPU-only, read-only on the repo)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s (cards 0+1). **Record:** **62.345282 tok/s** (packet190 k3x
chain, LocalMaxxing `cmvk51wfn001gng01fpbfy89q`). **Chain bar:** 63.592 (+2%). **Screen bar:** 62.657 (+0.5%).

Nothing here was built, run on a device, queued, committed or written into the repo. Every number is arithmetic on the
retained per-interval receipts: packet190's 12 × 99 record intervals (`build/device-cards01-p190-a/WS128/run/repeat-1`,
with `draft_rows.draft_wall_ms` and the rank-0 p150 scopes joined by position) and packet189's one-load bracket
(V3/k3x/V3/k3x/V3). Scripts beside this file: `model_k3x.py` (k3x critical-path model, every price and threshold; output
`model-k3x-output.json`, console copy `model-k3x-print.txt`), `dnr-list.txt` / `all-dnr.txt` (all 261 DO-NOT-REPEAT.md
files under `experiments/own-xpu-runtime`, 223 of them stage2 packets, collected before proposing anything),
`dnr-grep.txt` (the corpus grepped for every mechanism and closed family named below). The model reuses lever synthesis 2's
loader and record metric (`packet188 analysis/replay_v3.py`, imported read-only) and reproduces 62.345281904743764 to
1e-9 from the raw receipts.

## 0. Answer

* **A.** The k3x critical path per hit is `max(draft 1.531, boundary 1.483) + max(A 11.927, B 11.902) + G 0.038 = 13.509`
  and per miss `R 0.290 + C 11.666 + Bd 1.483 + max(B 12.052, A 11.926) + G 0.016 = 25.511` (99-interval window means;
  the receipts' all-127-cycle means are 13.528 / 25.546, the summary's medians 13.530 / 25.561). The identity reproduces
  every interval and the 62.345282 class-balanced metric exactly. **On hits the draft binds the ready side on 99.9% of
  intervals by 0.048 ms** (p5 0.026, p95 0.080) and **rank 0's A binds the race on 69% by 0.025 ms** (B binds the other 31%
  by 0.013 on average). Both ranks are 99.3–99.4% busy per hit (rank 0: Bd + A = 13.41; rank 1: D + B = 13.43 against a
  13.51 cycle): the hit cycle is now **half the total work of the two cards**, so no single-side cut can give more than its
  slack: draft-only saturates at **+0.23%**, A-only at **+0.20%**, B-only at **+0.19%**, boundary-only at 0 on hits. On
  misses rank 0's serial path (R + C + Bd = 13.44) binds the ready side by **11.91 ms** over the draft, rank 1 idles that
  long, and B binds the race on 90% by 0.125 (the warm-after-idle term). Critical-path shares of the record time:
  A 42.0%, B 32.3%, C 15.6%, D 7.5%, Bd-on-misses 2.0%, R 0.4%, G 0.2%.
* **B.** The two halves do **not** run the same layers: A/C are layers 0–23 (18 GDN + 6 QSA), Bd is 24–26 (3 GDN), B is
  27–47 (15 GDN + 6 QSA) + the 248,320-row head (1.40 ms). A per-GDN-layer saving δ therefore cuts A and C by 18δ, Bd by
  3δ and B by 15δ, and because both ranks are balanced it counts in full: **+1.32% per 0.01 ms/GDN-layer**; the chain bar
  needs **15.1 µs per GDN layer (3.2% of the 0.469 ms layer)** or 11.2 µs on all 48 layers; the screen bar needs 3.8 µs.
  A 0.1 ms/layer win on both halves would be +14% (GDN only) / +20% (all 48 layers), which only says how far the kernels
  are from such a number: the measured layer is 0.469 ms (boundary body / 3), 0.486 on rank 0's half, 0.495 on rank 1's.
  The largest class costs per GDN layer (packet110's measured complete-layer table at 128 tokens, current E1/route-fast/
  rec-both-plus selection) are experts gate/up + down 111 µs (excess over the 537 GB/s copy floor 74 µs), dense
  qkv + z + attention-projection 155 µs (excess 20), HC gates + norms + low 84 µs (excess 55), recurrence 24 µs (excess 18),
  route 19 µs (excess 19), small GEMVs 41 µs (excess ~10). Every class has a measured ceiling on the ledger: experts
  (packet65 wide64 in production, packet73 −, packet81 neutral, packet95 E2/E3 closed, packet104 tile16 arms 0.95–1.03,
  packet119 1.079×, packet162b 4.8× slower, packet173 E1n2 +0.22%), route (packet78 in production, packet112 missed its
  gate, packet164 gaps 0.003 ms/half), recurrence (packet82b in production, packet67 rec-head −11.8%, packet49d
  rows4/rows8 not selected by K2), HC (packet60/73 in production, packet94 norm-consumer fusion closed, packet122 0.913×,
  packet140 priors ≤ +0.3%), dense (packet74 −0.8/−2.4/−2.9%, packet183 S1 −6.2%, packet175 D2 1.44×, packet175b D1 1.07×),
  head (packet93 lane-A loss, packet161 argmax 99.99992% reads), QSA (packet107 loss), norms (packet78 −0.65%), layouts
  (packet142/145 null). The only class item without a measured row is packet110's #1 "exact gate/up tile16 with the
  half-cache (packet104b)": at 100% of its 0.893 operator ratio it is −6.5 µs/layer on 24 + 3 + 21 layers = **+1.16%**, and
  at the lab's 20% transfer rule +0.2%. **No open class mechanism prices at +2%.**
* **C.** The draft wall (1.531) is the binding ready term on 99.9% of hits, but only by 0.048 ms over the boundary
  (1.483): cutting D by x gives hits −min(x, 0.048) and then the boundary binds. Draft −0.02 → +0.10%, −0.05 → +0.21%,
  anything larger → **+0.23% (ceiling)**. The ledger closes the draft lane as a whole (packet158: kernel ≈ 1.38 ms, positive
  gaps ≈ 0.48 ms, host issue 0.42 ms nonblocking and already overlapped, "revisit only with a new mechanism removing a
  measured ≥ 0.42 ms/hit"), packet156 (suffix slack ≈ 0.3%), packet79/106b (relocation/split), packet114 (prefix 80,128
  immutable), packet108 (load8), packet122 (HC remap), packet161 (early argmax), packet126 (early draft). The 0.049 ms
  gained by `rank0_prepare=async` + kernel I/O is already in the record. Nothing on the draft side is both open and worth
  more than +0.23%; the `rank0_idle_waiting_for_guess` scope (mean 0.057 ms) is that whole ceiling, measured directly.
* **D.** A miss costs 25.51 vs 13.51 ms, so **+1 point of acceptance = +0.75%** (replay: +2 → +1.52%, +3 → +2.29%; the chain
  bar needs **+2.63 points**, the screen bar +0.67). No lossless acceptance lever is open: the MTP draft is already
  conditioned on the verified token (it runs after emission on the confirmed token and rank 1's final state; packet79/158),
  its arithmetic is fixed by packet129 ("no FP8/BF16 expert-format replacement, new quantization, acceptance tuning"),
  the prefix by packet114, prompt/n-gram lookup by packet146 (policy), out-of-prefix rescue by packet144 (+1.233% free
  upper bound, closed). **Width-2 at depth 1** (a second candidate verified in the same half) is closed three times:
  packet96 (held-out gain 0%; margin < 1 flags 58/256 misses, the second choice rescues 15 = +1.26 acceptance points =
  **+0.95% at zero cost**), packet132 (every active gate loses; bar: total M=2 cost ≤ 1.952 ms), packet151e (measured
  partial-M=2 half on device **+9.21 ms**, 4.7× the bar). Priced here with the second row on rank 0's A: **−1.95% at
  +0.5 ms, −9.95% at the 1.952 ms bar, −36% at the measured 9.21**. Depth 2 (packet71c −46.8%, packet66/68b) is the
  batched-rows family the brief names and is closed by its own rows.
* **E. Nothing open reaches +2%, and nothing open reaches +0.5% as a single mechanism.** Ranked (replay on the record
  intervals): balanced host-envelope trims draft −0.05 / A −0.05 / B −0.05 **+0.52%** (needs three mechanisms, one of
  them in the closed draft lane; without the draft part +0.31%); every envelope item at its measured size +0.77%;
  packet104b gate/up tile16 ≤ +1.16% at 100% micro transfer (+0.2% at 20%); restore R removed +0.38% (packet144 closed);
  warm-after-idle +0.10% (closed); draft ceiling +0.23%; A-only ceiling +0.20%; B-only (packet93 head) +0.19% (closed on
  lane A). Measurement noise on this line: k3x view-to-view 0.03% (per prompt ≤ 0.11%), V3 in-load drift 0.28%, fresh
  chain vs best screen view +0.17%. So the best open composite (+0.5%) sits at the screen bar and inside the noise of a
  single view pair, and each of its parts alone is within drift. **Recommendation: ONE measurement packet** (§5), an
  in-engine per-class attribution of both ranks under the k3x selection, because the only lever family that can still
  price at +2% is a both-halves kernel-class saving of ≥ 15 µs per GDN layer, and the line has no in-engine class table
  under its current selection (packet77's is bundle-6-era at 24/24, packet110's is a synthetic layer at the 10-18
  selection). Priced gain of that packet: 0 tok/s; it decides whether any kernel brief can honestly be priced ≥ +2%.

## 1. The k3x critical-path model (question A)

### 1.1 Topology and identity

Packet85's model was `hit = D → [Bh ‖ A]`, `miss = [D ‖ R→C] → [Bm ‖ A]`. Under V3/k3x rank 0 runs the boundary (layers
24–26 of the verified token, then the 20,480-byte copy-engine export) after the accept, while rank 1 runs the draft; rank 1's
half starts at layer 27 from the exported streams, and rank 0's next speculative half needs the guess. Both next halves start
at `ready = max(D, Bd)`: rank 1's B is queued behind the draft on its single in-order queue and rank 0's A waits for the
publication (`rank0_idle_waiting_for_guess_ms`, mean 0.057, is exactly D − Bd when positive). On misses rank 0 is serial.

```
hit  : T = max(D, Bd)            + max(B, A + offset) + G       D := draft_rows.draft_wall_ms (never op 9: 0.43 under async prepare)
miss : T = max(D, R + C + Bd)    + max(B, A + offset) + G
metric = per prompt 99000 / ΣT, median of class medians
```

`model_k3x.py` asserts that the identity with no deltas reproduces 62.345281904743764 (G is the signed residual; hit G mean
0.038, p5 0.006, p95 0.074; miss G 0.016).

### 1.2 Measured components (ms, packet190 record; packet189's two k3x views in brackets)

| | Hit (932 = 78.5%) | Miss (256) |
|---|---:|---:|
| D op 9 (host issue only, reported) | 0.427 | 0.426 |
| **D = draft wall** | **1.531** [1.532 / 1.532] | 1.532 |
| rank-0 idle waiting for the guess | 0.057 | 0.055 |
| **Bd boundary total** (body + export) | **1.483** = 1.406 + 0.058 [1.481] | 1.483 |
| R / C | 0 / 0 | 0.290 / 11.666 [0.290 / 11.699] |
| ready | 1.531 (draft binds 99.9%) | 13.439 (serial path binds 100%) |
| **A** (+ offset −0.0004) | **11.927** [11.955 / 11.956] | 11.926 |
| **B** | **11.902** [11.921 / 11.925] | 12.052 [12.078 / 12.075] |
| race | 11.940 (A binds 69%) | 12.056 (B binds 90%) |
| G | 0.038 | 0.016 |
| **elapsed** | **13.509** [13.530 / 13.532] | **25.511** [25.570 / 25.568] |
| rank-0 busy (Bd + A, or R + C + Bd + A) | 13.41 (99.3%) | 25.36 (99.4%) |
| rank-1 busy (D + B) | 13.43 (99.4%) | 13.58 (53%; idle 11.91) |

Envelopes: rank-0 A − `half_completion` = **0.267** (snapshot 0.250, token_prep 0.051; `prepare_ms` 0.051 now overlapped;
p76 retirement 0.098 is host work inside the layer body while the host waits 9.0 of the 11.7 ms); rank-1 B −
`half_completion` = **0.046** (retirement 0.040). Per layer: rank-0 half 11.660 / 24 = **0.486**; boundary body 1.406 / 3 =
**0.469** per GDN layer; rank-1 (11.856 − 1.404 head − 0.052 final norm) / 21 = **0.495**.

### 1.3 Binding and slack (per-interval distributions, hits)

| Slack | mean | p5 | p50 | p95 | min / max |
|---|---:|---:|---:|---:|---:|
| draft − boundary (D − Bd) | 0.048 | 0.026 | 0.045 | 0.080 | −0.130 / 0.144 |
| A + offset − B | 0.025 | −0.066 | 0.028 | 0.119 | −0.326 / 0.222 |
| usable if only A is cut (max(0, A − B)) | 0.038 | 0 | 0.028 | 0.119 | |
| usable if only B is cut | 0.013 | 0 | 0 | 0.066 | |
| usable if only D is cut | 0.048 | 0.026 | 0.045 | 0.080 | |
| usable if only Bd is cut | 0.0001 | 0 | 0 | 0 | |

Misses: serial path − draft = 11.91 (p5 11.83, p95 12.05); B − A = 0.125 (p5 −0.025, p95 0.337).

**Single-side ceilings (replay, cut to zero):** draft **+0.23%**, A **+0.20%**, B **+0.19%**, Bd +2.02% (all of it on misses, where the
boundary is serial: Bd −0.1 → +0.13%, −0.2 → +0.26%), C −1.0 ms → +1.34%. Lever synthesis 3's "+0.3 points" saturation is
confirmed by the record data: the two cards are balanced to 0.025 ms on the race and 0.048 ms on the ready side.

## 2. Both-halves levers (question B)

### 2.1 What a per-layer saving is worth now

Because A and B are balanced, a saving that lands on both ranks counts in full (per-interval replay, record intervals):

| Saving | hit ms | miss ms | gain |
|---|---:|---:|---:|
| 0.005 ms per GDN layer (A −0.09, C −0.09, Bd −0.015, B −0.075) | 13.424 | 25.330 | **+0.66%** |
| 0.01 ms per GDN layer | 13.341 | 25.149 | **+1.32%** |
| 0.0151 ms per GDN layer (**chain bar**) | 13.26 | 24.95 | +2.00% |
| 0.02 ms per GDN layer | 13.180 | 24.788 | +2.65% |
| 0.1 ms per GDN layer (the brief's number) | 11.971 | 21.907 | +14.1% |
| 0.01 ms per QSA layer (6 per half) | 13.449 | 25.391 | +0.46% |
| 0.01 ms on all 48 layers | 13.281 | 25.029 | +1.79% (chain bar: 0.0112 ms/layer) |
| 0.1 ms on all 48 layers | 11.371 | 20.707 | +20.3% |
| symmetric host trim x on A, B and C: 0.05 / 0.1 / 0.2 | | | +0.38% / +0.76% / +1.53% (chain bar 0.260 ms per half) |
| symmetric A, B, C and D: 0.05 / 0.1 / 0.2 | | | +0.59% / +0.99% / +1.77% (chain bar 0.229) |

Thresholds: **+2% = 15.1 µs per GDN layer = 3.2% of a 0.469 ms layer**; **+0.5% = 3.8 µs per GDN layer (0.8%)**. A class has
to lose that much per layer on *both* ranks, exactly.

### 2.2 Class costs per GDN layer and the ledger's measured ceilings

Per-class µs per call from packet110's complete-layer measurement (ROOFLINE.md, GDN at 128 occupied tokens, the current
E1 half-cache / route-fast / rec-both-plus / wide-HC selection; "excess" = measured − bytes/537 GB/s, a reference gap, not a
realizable saving). K2's receipts in the record chain (`K2/run0/summary-k2-measured.json`, `dispatch-measured.json`) are
selection micro-fixtures (e.g. expsgate 165.8 µs per fixture token against the engine's ~60 µs per layer) and confirm only
*which* kernel each class runs (expsgate `p28.paired.wg32`, expsdown `p33.down.bank`, gdn.qkv/z `p33.dense.segment`,
recurrence `round2`, route `p42.route.production_rank32`, attention `p28.dense.wg32`, HC gates `p33.dense.segment`); they are
not per-layer engine costs and are not used as such here.

| Class group (per GDN layer) | µs/layer | excess µs | ×18 excess ms/half | +2% needs (15.1 µs) | Ledger ceiling / closure |
|---|---:|---:|---:|---|---|
| experts gate/up (60.4) + down (50.9) | 111.3 | 73.9 | 1.33 | 13.6% of the class | packet65 wide64 won (in production); packet73 experts2 lost; packet81 load-count neutral; packet95 E2 closed (memory), E3 closed at its negative engine result (packet100); packet104 tile16 arms 0.95–1.03 (closed); packet119 down-warm 1.079× closed; packet162b IQ2 lookup 4.8× slower; packet173 E1n2 prior +0.22%; packet102/115 ILP/GRF no measured win. Open on paper: packet110 #1 "gate/up tile16 + half-cache (packet104b)" at a 0.893 operator ratio = −6.5 µs/layer → **+1.16% at 100% transfer, +0.2% at 20%** |
| dense gdn.qkv (68.6) + gdn.z (39.6) + attention proj (46.7) | 154.9 | 20.3 | 0.37 | 9.7% (floor allows 13%) | packet74 packed −0.8/−2.4/−2.9%; packet183 S1 −6.2% (S2 with it); packet175 D2 1.44×; packet175b D1 1.07×; "already near their measured bandwidth limit" (packet113) |
| HC gates (44.8) + norms (17.4) + low (21.6) | 83.8 | 55.1 | 0.99 | 18% | packet60 three-kernel fusion and packet73 hc-wide (+0.73%) in production; packet94 norm-consumer fusion closed (packet110 exclusion); packet122 HC remap 0.913×; packet117; packet140 N1/N3/G1 priors +0.24–0.28%; packet67 four-stream −6…−22% |
| recurrence (24.0) + conv (9.3) + gated (5.2) | 38.5 | 32 | 0.57 | 39% | packet82/82b rec-both-plus in production; packet67 rec-head −11.8%; packet49d rows4/rows8-shared measured, K2 keeps `round2`; "approximate gate math / reordered reductions excluded" |
| route (18.75) + router/shared small.ffn (19.0) + moe/combine (16.4) | 54.1 | 35 | 0.63 | 28% | packet78 route-fast in production; packet112 pruned top10 missed its kill gate; packet164: visible gaps 0.003 ms/half, "not identifiable"; packet109 epilogues already selected (`p39.epilogue`) |
| small GEMVs (gdn.ab 6.8, shexp 15.2, hc.low in HC) | 22 | ~9 | 0.16 | 69% | p30/p49d small tuples in production; nothing left above the floor |
| QSA layer (6 per half, ~519 µs; qsa.attention 52 at 128 ctx → 610 at 4096) | — | qsa.attention 51 | 0.31 (6 layers) | — | packet107 local sharing lost; packet116 schedule; context-dependent (grows with prompt length; the suite is 60–90 prompt tokens) |
| head (rank 1 only, 1.404 ms, 566 GB/s) | — | −28 (under the copy floor) | — | B-only: ceiling +0.19% | packet93 transpose lane-A loss (review 15, packet105); packet161 argmax |
| draft (rank 1 only, wall 1.531; kernel ≈ 1.38) | — | gaps 0.48 | — | D-only: ceiling +0.23% | packet158 lane closure |

Reading: the sum of all class excess over the copy floor is ≈ 4.4 ms per half, but every class has been worked and the
measured arms that remain selected are in the line. The one class item with no measured row (packet104b) is below +2%
even at 100% micro transfer, and packet104's measured tile16 siblings came in at 0.95–1.03. **There is no open both-halves
kernel lever priced at +2%**, and the ledger's revisit conditions for the big classes (experts, HC, route) all ask for a
new mechanism with in-engine causal evidence, which is the measurement in §5.

## 3. Draft-side levers (question C)

Is the draft wall the binding term? Yes on hits: `max(D, Bd)` picks D on 931/932 intervals, by 0.048 ms (p5 0.026). It is
*not* binding by much: cut D by x and the hit cycle falls by min(x, D − Bd) per interval, then the boundary (1.483) binds.
Replay: D −0.02 → +0.10%, −0.05 → +0.21%, −0.10 → +0.23%, −0.42 (the old packet147 +2% threshold) → +0.23%. On misses D
is irrelevant (the serial path is 11.9 ms longer). So **the draft ceiling is +0.23%**, and the measured
`rank0_idle_waiting_for_guess_ms` (0.057 mean, 0.105 p95) is that number observed directly on rank 0.

What is open on the draft: nothing worth that ceiling. The DNR corpus closes depth-2 (packet66/68b/71c), draft on rank 0
(packet79), Q4 / draft bytes (packet83 via packet90, packet108 load8), the smaller/independent prefix (packet114: 80,128 is
immutable; packet156), the draft kernel path and host issue as a lane (packet158: "no packet159 draft build and no further
draft diagnostics"; revisit only with ≥ 0.42 ms/hit), the readback/publication path (now kernel I/O: the 0.049 ms of the
packet188/189 trims is in the record), early argmax (packet161), the draft head on rank 0 (packet160/106b: +1.3% on V3,
−0.97% once k=3 holds the window). The draft's own argmax is 0.026 ms and the publication 8 bytes; its host issue (0.42 ms)
is nonblocking and overlapped with the draft kernels (op 9 returns at 0.43 while the wall is 1.53). Conclusion: **no draft
lever is both open and above +0.23%**, and the ceiling itself is inside single-view noise (±0.1–0.3%).

## 4. Acceptance-side levers (question D)

Replay with the expected flip of 0.99 × points intervals per prompt from miss to hit (hit proxies for B and G per prompt):

| Acceptance | gain | | Width-2 at depth 1 (second candidate row on A, rescues 15/256 misses = +1.26 pts) | gain |
|---|---:|---|---|---:|
| +1 point | **+0.75%** | | extra row free (impossible) | +0.95% |
| +2 | +1.52% | | extra row +0.5 ms per interval | −1.95% |
| +2.63 (**chain bar**) | +2.00% | | +1.0 ms | −4.86% |
| +3 | +2.29% | | +1.952 ms (packet132's bar) | −9.95% |
| +5 | +3.88% | | +9.21 ms (packet151e measured partial M=2) | −36.0% |

Lossless ways to raise acceptance: none open. The draft is the official MTP head (draft-only 8-bit requantisation) and is
already conditioned on the verified token and rank 1's final state (that dependency is why packet79's rank-0 draft lost);
changing its weights/format changes proposals (packet129 closes acceptance tuning and expert-format replacement), the
prefix is immutable (packet114), n-gram/prompt lookup is policy-closed (packet146), miss-conditioned completion of the
omitted head rows is a free upper bound of +1.233% (packet144, closed). Width-2 is closed by packet96 (held-out 0%),
packet132 (every active gate loses; revisit only with total M=2 cost ≤ 1.952 ms) and packet151e (device cost +9.21 ms,
4.7× the bar); its best case is +0.95% at zero cost, so even a new cost mechanism cannot reach the chain bar. The
batched-rows family (H(2)/H(1) of packet68b; packet71c depth 2 −46.8%) is closed by the same arithmetic: a second row in
A costs more than the misses it rescues, because A binds the race.

## 5. Ranking and the one next packet (question E)

| # | Lever (open status) | Arithmetic | Price | Bar |
|---|---|---|---:|---|
| 1 | Balanced host-envelope trims: draft −0.05, A −0.05, B −0.05 | hits: ready −0.048 (then Bd binds), race −0.05; misses: B −0.05 | **+0.52%** (range +0.31% without the draft part … +0.77% with every envelope item: A −0.10, B −0.06, C −0.05, D −0.05) | screen only; three mechanisms, each ≤ +0.23% alone (inside drift); draft part is in a closed lane |
| 2 | packet104b gate/up tile16 with the half-cache (open on paper, packet110 #1) | −6.5 µs/layer at the 0.893 micro ratio on 48 layers | **≤ +1.16%** at 100% transfer; **+0.2%** at the lab's 20% rule | screen at best; packet104's three measured tile16 siblings were 0.95–1.03 |
| 3 | A-only envelope (snapshot 0.250 off A's path, e.g. on the copy queue during the boundary) | race slack 0.038 mean | **+0.14…+0.20%** (A −0.05 … −0.25) | below; not DNR-closed (packet177 row 3 names "a BCS queue" as its revisit condition; packet58al forbids compute on BCS, not copies; packet88 closes restore-on-BCS, not capture) |
| 4 | Draft cut of any size | D − Bd slack 0.048 | **≤ +0.23%** | below; lane closed (packet158) |
| 5 | B-only: packet93 head transpose (−0.38 micro) | B binds 31% of hits by 0.013; misses −0.13 | **+0.19%** | below; closed on lane A |
| 6 | Miss path: R removed / warm-after-idle removed / C −1 ms | 0.216 × 0.290 / 0.150 / 1.0 ms | +0.38% / +0.10% / +1.34% | closed (packet144, packet148); C-only chain bar 1.48 ms/miss |
| 7 | Acceptance +1 point | 0.99 flips × 12.0 ms per prompt | +0.75% / point | no lossless lever open (§4) |
| 8 | Width-2 at depth 1 | §4 | −1.95% … −36% | closed (packet96/132/151) |
| 9 | Boundary cut (copy export already 0.058) | hits 0; misses −x | +0.13% per 0.1 ms | nothing left to cut (body is three layer bodies) |
| 10 | Rebalance between ranks (any direction) | hit slack 0.025 / 0.048 | ≈ 0 | the line is at (A + Bd + D + B) / 2 |

**Reaches +2%:** nothing. **Reaches +0.5%:** only the three-mechanism composite #1 (and #2 only at an unsupported 100%
transfer). Noise: k3x view-to-view 0.03%, per-prompt ≤ 0.11%; V3 in-load drift 0.28%; chain vs screen +0.17%. #1 is at
the screen bar and inside the noise of a single candidate/control pair; its parts are individually within drift.

**Why the hit path is at a floor:** T_hit = 13.51 ≈ (rank-0 work 13.41 + rank-1 work 13.43) / 2. Only a cut of *total*
work moves it, and the total is 24 + 3 + 21 layer bodies (0.47–0.50 ms each, every class closed or at its measured ceiling),
one head (at the copy floor), one draft (lane closed), 0.31 ms of host envelope and 0.04 ms of gaps. **Why the miss path is
at a floor:** 25.51 = R 0.29 + 48 serial layer bodies + head + 0.15 warm + 0.02 gaps; rank 1's 11.9 ms idle per miss can only
be used by weights rank 1 does not hold (packet148: a layer is 1.13 GB against 0.63 GB headroom), and moving the three
boundary layers to rank 1 on misses saves nothing because the chain stays serial (−1.48 + 1.39 + 0.05 = −0.04 ms).

### The one next packet: `packet191-k3x-class-attribution` (measurement, lane B, < 20 min)

Purpose: the only lever family that can still price at +2% is a both-halves kernel-class saving of ≥ 15.1 µs per GDN
layer (or 11.2 µs per layer on all 48). The line has no in-engine per-class table under its current selection: packet77's
attribution is bundle-6-era (24/24 split, old kernels), packet110's is a synthetic complete layer at the 10-18 selection, the
record chain's `sites.jsonl` are empty (p150 scopes only). The ledger's revisit conditions for experts, HC and route all ask
for in-engine causal evidence. This packet produces it and either opens one priced kernel brief or closes the lane honestly.

* **Selection keys:** the packet190 k3x record selection unchanged (`rank0_layers 0-26`, `boundary rank0-k3`,
  `kernel_io kernel`, `rank0_prepare async`, `boundary_export copy`, `snapshot_host static`, head un-split, K2 dispatch as
  measured) plus the packet77 per-class site instrumentation (`sites.jsonl`) on **both** ranks as an execution-time view key
  (`attribution=sites|off`), switchable in-load like `kernel_io`. Sampled layers: one GDN and one QSA per rank per view
  (rank 0: 22 and 23 as packet77 did, plus boundary layer 26; rank 1: 28 and 27), all 24 call sites per layer, every
  event summed per class per call before medians (packet110 rule). No new kernels, no selection change.
* **Rows (lane B, PAUSE-A held), ≈ 14 min:** row 0 smoke `attribution=sites`, 12 × 64 + incident64, exact (~5 min);
  row 1 ONE load `off / sites / off / sites / off`, 12 × 128 each (~8 min; packet189's bracket took 476 s).
* **Decision rule:** report per rank and per class: ms per half (occurrences × median call), excess over the copy floor
  (packet110 byte model) and over packet110's synthetic call time; the instrumented/control ratio must be ≥ 0.93 on
  every view (packet77 measured 0.954) or the table is not admissible. A class **qualifies for a lever brief** only if its
  in-engine excess per GDN layer ≥ 15.1 µs on both ranks (chain bar) or ≥ 3.8 µs (screen bar) **and** a mechanism exists
  that no DNR row closes; the brief must quote that row search. Nothing in this packet is a speed result.
* **Kill rules:** (1) any view not 13/13 exact or proposals/acceptance not identical → stop; (2) control drift > 0.5%
  across the three `off` views → stop (instrumentation leaking into the controls); (3) instrumented/control < 0.93 → the
  table is reported as inadmissible; (4) class sums per layer differing from `layer_body` / 24 by > 10% → stop (missing
  events, packet157's "do not treat missing streams as zero").
* **Priced gain:** 0 tok/s (measurement). Expected outcome, honestly: the synthetic table already shows every large excess
  sitting in classes with measured closures; the most likely result is a confirmation that no class has ≥ 15 µs/layer of
  excess reachable by an open mechanism, which closes the two-card kernel lane at 62.35 until a new mechanism exists.
  The alternative outcome that would matter: an in-engine excess in a class where the synthetic fixture under-represents
  the engine (QSA attention at long contexts, HC gates, route), with ≥ 0.27 ms per half on both ranks.

**If a screen is wanted instead of a measurement**, the only priced candidate is #1 at +0.52% (keys: the record selection
plus `snapshot_copy=overlap` for the 19.0 MB capture on the copy queue during the boundary, a rank-1 retirement trim, and
the draft issue trim; rows as packet189; decision ≥ 1.005 × every control view; kill: A − half_completion not reduced by
≥ 0.15, B envelope not reduced by ≥ 0.03, draft wall not reduced by ≥ 0.03). Its honest range is +0.31…+0.77%, it cannot
chain, and its draft part needs a ruling against packet158's lane closure.

## 6. Rows checked (`dnr-grep.txt`; all 261 DO-NOT-REPEAT.md files)

Closed families named in the brief and respected here: depth-2 / batched draft rows (packet66, 68b H(2)/H(1), 71c
−46.8%); draft on rank 0 (packet79); packed dense reads (packet74, packet93/93x, packet90 "no packet74 packed dense");
draft bytes / Q4 / smaller prefix (packet83 via packet90, packet108, packet114, packet156); expert load-count (packet81,
packet108, packet175b); miss path (packet144 all rows, packet148, packet121); roofline-picked HC/recurrence kernels
(packet67, packet82/82b, packet113); S1/S2 dense scales (packet183); class-layout / kernel-order layouts (packet142, 145);
k=3 with a kernel export (packet188 "LOSS, closed as built"; packet189 "do not route a device→host readback of more than a
few hundred bytes through KioCopy"); QSA layers in the boundary (packet188/189 "do not add QSA layer 23 or 27");
replay/graph recording (packet34); merged serial kernels (packet37/45, one-card era). Also: second candidate / sibling
(packet96, 132, 151, 151d); acceptance (packet129, 114, 146); draft lane (packet158, 157, 154, 122, 126, 161); placement
(packet177 row 2 as ruled for V3/k3, packet120, 186 "do not run the moved layers inside a speculative half", 185 no in-load
head switch); two-card copies (packet177 row 3: "revisit when … a BCS queue is introduced"; the one-card packet58al row
"do not issue compute on BCS or assume a second CCS; a copy queue is not another physical copy engine" concerns compute,
not copies; packet88's "do not create R/D overlap by moving rank-0 restore to BCS: cross-card overlap already exists" is
about the restore, which is already overlapped); packet190's chain boundaries (k3 storage needs `--pipeline-mini5`,
KD projection of the k3 keys, disk margin) apply to any chain derived from this line. No row closes an in-engine per-class
attribution view on the k3x line; packet77 is its precedent.

## 7. Scripts

* `model_k3x.py` — loads packet190's 1,188 record intervals (+ draft wall, rank-0 idle, p150 scopes, rank-0/rank-1 half
  host fields) and packet189's five views; asserts the record replay and the model identity; prints §1 (components,
  binding, slack, busy, critical-path shares), every price in §2–§5, the +2% / +0.5% thresholds and the single-side
  ceilings; writes `model-k3x-output.json` (console copy `model-k3x-print.txt`).
* `dnr-list.txt`, `all-dnr.txt`, `dnr-grep.txt` — the DO-NOT-REPEAT corpus and the grep used for §6.
