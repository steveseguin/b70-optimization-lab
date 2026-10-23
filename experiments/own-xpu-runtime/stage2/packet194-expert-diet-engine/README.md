# Packet194: the exp-diet gate/up kernel in the k3x record engine, behind `expert_gateup=production|diet` (CPU-prepared, device pending)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s. **Record:** 62.345282 tok/s (packet190 k3x chain,
LocalMaxxing `cmvk51wfn001gng01fpbfy89q`; selection packet189 `k3x` c5443bbf…, engine 87eec645…). **Chain bar:** 1.02 ×
62.345281904743764 = **63.59218754283864 tok/s**. **Screen bar:** +0.5 % over every k3x view.

**Status:** prepared CPU-only, READY for a lane-B device window (`READY-FOR-DEVICE.json`, written last). Nothing was
queued, armed, launched or committed. No GPU, `/dev/dri`, device binary run, systemd unit change, PAUSE/STOP or queue file
was touched. The only systemd calls were read-only `systemctl --user list-units` polls before each compile batch
(`v5/evidence/compile-poll.json`; the owner's endpoint-restore window `window-p193-driver …-restore19` was active and is
tolerated by the brief). The proposal is `ops/lane-queue/proposed-p194-two-card-B.txt` (PROPOSAL ONLY; mirror `proposals/`).

## Ruling (coordinator, 2026-10-23, quoted)

> "packet193 measured the exact gate/up instruction diet at 0.78× production cold and 0.77× warm on card 2, byte-identical
> on every claimed stratum. Integrate `exp-diet` into the k3x record engine as an in-load key `expert_gateup=production|diet`
> (production = byte-for-byte the record kernel), prove engine-level exactness on CPU, and screen it on lane B with a one-load
> bracket k3x / k3x+diet / k3x / k3x+diet / k3x. Screen winner at ≥ +0.5 % over every k3x view; chain rule at ≥ +2 % over
> every k3x view AND ≥ 63.592 tok/s. Kill rules: any inexact view; proposals or acceptance differ; k3x drift > 0.5 %; the
> diet's per-layer gate/up saving (from the p150 scopes or the class attribution of packet191 if cheap) < 5 µs."

Packet193's device evidence (`../packet193-expert-diet/evidence/diet-B1/samples.jsonl`, `window.json`; lane B, card 2,
lanequeue-B39, 2026-10-23 04:27 UTC): every claimed stratum byte-identical on device for every candidate; exp-diet gate/up
cold **57.92 vs 73.85 µs** (0.784 in both orders), warm **35.99–36.15 vs 46.77** (0.769–0.773): **15.9 µs (cold) to
10.8 µs (warm) saved per gate/up launch**. exp-act-epilogue (0.82/0.85) gained nothing over exp-diet plus the separate
activation launch and was dropped; down-diet (0.96) failed the bar and was closed. The wrapper's stop was the PRODUCTION
kernel's NaN-payload order against a GNU CPU fixture on the NaN-only diagnostic stratum (coordinator ruling: diagnostic,
not an exactness failure).

## What changed from packet189 (the record engine)

Base: packet189 (`copy_packet194.py`, receipt `lineage/packet194-copy.json`: 2,217 files, 265 identity rewrites, 1,517
hard-linked history files, one history file rewritten for its identity literal). The packet189 binary lineage is kept: 76 of
the 78 pinned parent objects are relinked unchanged with their pins verified; **four TUs are rebuilt** (packet189 rebuilt
three): entry-main, p49d_submit, s1_submit and — the one TU the new kernel touches — `p49d_expert_submit`, which was a
pinned packet103 object in packet189 and is compiled here with packet103's recorded flags.

**1. The kernel.** `native-base/…/packet194-expert-diet-engine/p193_diet.hpp` is packet193's header **byte for byte**
(sha256 `aab37609be226ead4a255a44d87c1afb93e6d64d7819457c4aeecd33bcb750d8`, pinned in `v5/evidence/build.json`; not
re-derived). Only `p193diet::GateUp` (exp-diet) is dispatched; the header's three other kernels (the dropped
`GateUpAct`, `Down` and the activation twin) are compiled into the device image but never selected (the production-shape
launch census shows which kernels run).

**2. Registration and the key** (`v5/p194-native.patch`, **+57 / −16 lines in 7 files**, diffed against packet189 after
the identity rewrite; plus the pinned header and the new CPU fixture):

| File | Change |
|---|---|
| `p49d_expert_submit.cpp` | `#include p193_diet.hpp`; **Arm 13 = `p193diet::GateUp`** beside Arm 10 = `p90exp::Kernel<IQ2_S,2560,64,false,true>` in the `issue<>` candidate chain (same `p90::expert_stride` rows, same `p90exp::validate`, same WG64 grid, same `exceptional` semantics); a six-argument `p49d::expert(d, m, kind, b, experts, gateup)`: `production` and every down launch return the unchanged five-argument record dispatch; `diet` with `exp-halfcache` returns `chosen_expert<13>`; `diet` on any other gate/up layout and any unknown value refuse |
| `p49d_submit.hpp` | the six-argument declaration |
| `p49d_submit.cpp` | `resolve("expert_gateup", production\|diet)`; k3-storage selections may carry **20 keys** (19 + `expert_gateup`); the 19-key record selection still parses (key absent = production); the key is projected out of the target-only check |
| `v5/native/engine_bracket.hpp` | `expert_gateup` is a k3-storage key: domain `{production, diet}`, **switchable in-load** with `boundary`/`kernel_io`/`rank0_prepare`/`boundary_export`, refused in the 0-25 storage; `refresh_v3` sets `expert_diet` (default production when absent); per-prepare counters `expert_diet_sites` (gate/up sites prepared with the diet kernel: the exp-halfcache IQ2_S layers) and `expert_diet_inert_sites` (gate/up sites on another layout that keep their kernel: the IQ3_S p28 layers at production shape, every miniature expert) |
| `v5/native-src/main.cpp` | `expert_gateup_for(launch, kind, p49d_site)`: `"diet"` only for an `expert_gate_up` launch on the p49d (exp-halfcache) path, counted; a diet with a non-halfcache `experts` choice refuses outside the miniature; the dispatch-registry gate/up sites are counted as other-layout sites; the `p49d::expert` call passes the key |
| `v5/native/full_shape_entry.cpp` | the diet views of a load capture the other gate/up kernel (alternate capture must differ from the start capture and recapture identically); **a selected diet with zero diet sites refuses** (never silently inert); `v3-load.json`/result carry `expert_gateup` and the counters; one more native refusal (`expert_gateup: unknown`; 23 per run) |
| `v5/native/v3_state.cpp` | the result records `expert_gateup` and the two counters |

How the key switches: a bracket view loads a 20-key selection; `bracket_select` accepts the `expert_gateup` change on the
k3 storage, `refresh_v3` sets `expert_diet`, and `prepare_commands` re-prepares every site, so each exp-halfcache
`expert_gate_up` launch is captured with `p193diet::GateUp` (diet) or `p90exp::Kernel` (production). The IQ3_S expert
layers (p28 registry kernels) and the down kernel are untouched in both views.

**Selections** (`v5/lineage/<name>/selection.json`):

| Name | sha256 | Keys | Role |
|---|---|---|---|
| `v3` | `923639a9…` | 16 | packet187 record line (CPU identity gates only) |
| `v3k` | `92f5fcf7…` | 19 | packet189's V3 views of the k3 storage (CPU gates only) |
| `k3x-record` | **`c5443bbf…`** (= packet189 `k3x`, unchanged) | 19 | **the record selection**; loads on the new engine unchanged (key absent = production); CPU gates prove it is the record path |
| `k3x` | `c20504b7…` | 20 | the bracket's control: k3x-record + `expert_gateup production` |
| `k3x-diet` | `eb417ec9…` | 20 | the candidate: k3x + `expert_gateup diet` |

## Binary and changed TUs

| Item | Value |
|---|---|
| Device engine `v5/build/device/own-rt-iq3` | **`b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc`** |
| CPU twin `v5/build/gnu-host/own-rt-iq3` | `5d8f3c057ccbe2214da30bbf98f656f23d63653db328c64102cfdf59425720db` |
| Build | 10 compiler runs, 0 warning lines, 76 inherited parent objects pinned, 2 replaced (packet103's gnu-host and device `p49d_expert_submit.o`) (`v5/evidence/build.json`) |

## The exact-identity argument (carried from packet193 README §2, proved again at engine level here)

* **Kernel level (packet193).** exp-diet keeps production's loads and load widths and the per-chain FP32 sequence
  `v = scale·float(q)`, `product = v·input`, `sum = sum + product` in the same order, no contraction, no reassociation.
  (iii) the per-tile `exceptional` test is hoisted to one uniform test per 256-weight step because `exceptional ⇔ d
  non-finite` (a finite `d` times `0.5+sub ≥ 0.5` times `0.25` is finite or ±Inf, never NaN); the exceptional arm keeps
  production's `decode_tile` verbatim. (i) the sign is applied to the decoded weight after the scale multiply: every IQ2_S
  grid magnitude is in {8, 25, 43}, so `q ≠ 0`, and IEEE RN multiplication is sign-symmetric, so `scale·float(−q) ==
  −(scale·float(q))` bit for bit including `±0`/`±Inf` (NaN cannot occur on the normal arm); the negation precedes the input
  multiply, so `product` and the sum are production's operations on identical operands. (iv) the four effective scales of
  a step are pure CSE. Proved by packet193 on both host twins (3,146 claimed rows), by the random stress (100,000 IQ2
  blocks bit-exact) and **on the device** (every claimed stratum byte-identical, 384 real routes, warm, real rows).
* **Production kernel identity (this packet).** `v5/kernel_identity.py`: the device bitcode of packet103's pinned
  `p49d_expert_submit.o` and of the rebuilt object are split per kernel (`sycl-post-link -split=kernel`) and compared as
  SPIR-V text: **all 25 inherited kernels are present under the same names, opcode-identical and canonically identical**
  (globals/entry points by name, ids renumbered, literals kept), including the record gate/up kernel `p90exp::Kernel<IQ2_S,
  2560,64,false,true>` and the down kernel `p100::Kernel<2>`; exactly four kernels are added, all `p193diet`
  (`v5/evidence/kernel-identity.json`). Whole-object bytes cannot be compared (the bundle carries include paths).
* **Engine dispatch (this packet).** `v5/native/diet_fixture.cpp` drives the real `p49d::expert` with the record selection
  string `exp-halfcache+down-tile16` and `expert_gateup` = production / diet on GNU and Intel host twins: packet162b's real
  layer-0 and layer-24 rows (10 experts × 640 rows × two streams, normal / partial routes / NaN inputs) and synthetic
  exp-halfcache banks (normal, invalid expert, inactive, error-preset, partial routes, NaN, Inf, subnormal inputs): **14
  strata, every byte of y / peer y / status / peer status / error / active / position equal, 0 payload-order rows** on both
  twins; the six-argument production equals the five-argument record dispatch on every stratum; `diet` on a `wide64` layout
  and an unknown value refuse without writing (`v5/evidence/diet-fixture.json`).
* **Production shape (this packet).** `v5/p194_v5_full_shape.py`: the 20-key `k3x` load captures **exactly** packet189's
  k3-storage capture (so does `v3k → k3x-record`, and `v3` captures packet187/189's record-line capture); in the
  `k3x → k3x-diet` and `k3x-diet → k3x` loads the diet views recapture identically and differ from the production views
  **only in the kernel of the exp-halfcache `expert_gate_up` sites** (`p193diet::GateUp` vs `p90exp::Kernel`; every binding,
  shape and every other command identical; the IQ3_S p28 gate/up sites unchanged); device census identical for every
  k3-storage load (**diet delta 0 B per rank**); 23 native refusals per run; real-parser startup of all five selections on
  both ranks reproduces the census (`v5/evidence/full-shape.json`).
* **k3 state and the key (this packet).** `v5/k3_state_gate.py`: the miniature engine with `k3x-record` (19 keys),
  `k3x` and `k3x-diet` (GNU) and `k3x-diet` (Intel): 65 cases, 68 guard refusals, 2 detecting negatives each, **canonical
  transcript `d451302d…` = packet189's record k3x transcript for every run** (the key and the new engine move no byte;
  copy-engine export only); the two-rank five-layer miniature one-load brackets `k3x/k3x-diet/…` in both start orders
  equal the fresh production-layout reference (tokens, 120 per-step per-layer fixtures, proposals, draft and target
  state). The miniature has no exp-halfcache layout, so the diet is **inert there and counted** (`expert_diet_inert_sites`
  > 0, `expert_diet_sites` = 0); at production shape a selected diet with zero diet sites refuses (the full-shape fixture
  requires `expert_diet_sites > 0` in every diet view; the IQ3_S p28 gate/up layers are counted as other-layout sites and
  keep their kernel, as the launch census shows).

## Device rows (proposal, lane B, PAUSE-A held)

| Row | Job | What | Expected (s) | Watchdog | Writes |
|---|---|---|---|---|---|
| 0 | `packet194-row0-smoke-k3x-diet-B` | k3x-diet smoke, 12 × 64 + incident64, exact, first-request data proof | [270, 420], ~313 | 3600 | 240 MB |
| 1 | `packet194-row1-bracket-k3x-diet-B` | ONE load: k3x / k3x-diet / k3x / k3x-diet / k3x, each 12 × 128 + incident64 | [460, 900], ~476 | 3600 | 1.2 GB |

Expected times are packet189's recorded lane-B rows (smoke ~313 s, bracket 475.7 s; the storage and request mix are
identical, the diet only shortens gate/up kernels); total ~850 s (14.2 min) with the 61 s drain spacing: under 15 min.
Row 1 depends on row 0. The private-copy `lanequeue.py plan --lane B` and the entry rehearsal passed (`v5/evidence/plan-B.log`,
`rehearse.json`).

**Decision `s194_decision`** (in the row-1 summary, or `python3 -B v5/s194_decision.py <rows 0..1>`):

* **Screen winner:** every view 13/13 exact (smoke 12/12 × 64 + incident); draft proposals and per-prompt acceptance
  identical across the five 128-token views; k3x drift ≤ 0.5 % over the three in-load k3x views; the per-layer gate/up
  saving ≥ 5 µs on both ranks; AND the slower k3x-diet view ≥ 1.005 × every k3x view.
* **Chain rule:** the same AND ≥ 1.02 × every k3x view AND ≥ 63.59218754283864 tok/s.
* **Kill rules** (each blocks the verdict and is recorded): inexact view; proposals differ; acceptance differs; k3x drift
  > 0.5 %; gate/up saving < 5 µs per layer (`min(rank 0 ΔA/24, rank 1 ΔB/21)`, hit means; also reported: rank 0
  `layer_body`/24, boundary `boundary_body`/3, miss ΔC/24). **Caveat:** the scopes and rank traces are host-side; they
  attribute the whole half, not a kernel clock.
* **Priced** (lever synthesis 4: +1.32 % per 0.01 ms per GDN layer on both ranks): **+1.4 % at 10.8 µs (warm) to +2.1 %
  at 15.9 µs (cold)**; the chain bar needs 15.1 µs per GDN layer, the screen bar 3.8 µs. The engine regime sits between the
  two strata; the screen decides.
* **Tested on REAL data** (`v5/test_s194_decision.py`, 12 tests; `v5/evidence/analysis.json` pins every file it reads in
  place): packet189 row 1's own k3x views (62.242 / 62.225 tok/s, the record line) as both control and candidate → **NOT A
  SCREEN WINNER** (null; the saving rule fires at ~0 µs); the record-line V3 views as candidate → not a winner; scalings of the
  real k3x views with an injected 12 µs/layer saving → chain at +2.5 % and +2.2 %, winner-only at +2.15 % (63.580 < 63.592)
  and +1.5 %, not a winner at +0.4 %; drift 0.6 %, an inexact view, changed proposals/acceptance, a 3 µs saving, an
  unmeasured saving, a missing smoke and a wrong variant each refuse. packet190's 12 real WS128 streams reproduce the
  **record 62.345281904743764** (`RECORD` equals the stored class-balanced median) with the k3x hit/miss/boundary picture.

## Memory and host admission

Identical to packet189 (`v5/evidence/full-shape.json`, `admission.json`): k3 storage rank 0 **31,374,119,922 B**
(headroom 838,134,798 B under the 32,212,254,720 B arena limit), rank 1 **31,581,735,626 B** (headroom 630,519,094 B);
pinned kernel-io staging 86,016 + 73,728 B (host); speculative image 19,025,640 B / 984 extents. **The diet adds 0 B per
rank** (the full-shape census of the diet loads equals the k3x loads'). Host MemAvailable at START: **108,797,048,558 B**
(= packet189's k3x rows), plus the queue's 1 GiB. No change.

## Gates (receipts under `v5/evidence/`; all CPU, `nice -n 19 taskset -c 8-15,24-31 python3 -B … </dev/null`)

| Gate | Result | Receipt |
|---|---|---|
| Build (4 TUs × 2 modes + 2 links, unit poll) | PASS: 10 compiler runs, 0 warnings, 76 parent objects, 2 replaced, header pin | `build.json`, `compile-poll.json` |
| Kernel identity (pinned vs rebuilt device object) | PASS: 25/25 opcode- and canonically identical, +4 p193diet | `kernel-identity.json` |
| Diet dispatch fixture (GNU + Intel, real rows) | PASS: 14/14 strata byte-equal, 0 payload-order, 6 refusals, record = production | `diet-fixture.json`, `diet-fixture-*.log` |
| Production-shape startup | PASS: 4 loads × 2 ranks, 10 real-parser startups; captures/census = packet189; diet = gate/up kernels only, 0 B; 23 refusals | `full-shape.json`, `shape-*.tar.gz` |
| k3 state + key identity | PASS: 4 engine runs, canonical = packet189's `d451302d…`; 44 pipeline requests | `k3-state.json`, `k3-state-engine-*` |
| Admission | PASS: host 108,797,048,558 B; diet delta 0 B | `admission.json` |
| Analysis (schema, s194 on real packet189/190 data, price) | PASS: 3 test files | `analysis.json`, `analysis-real-inputs.json` |
| Controller mock, safety, exec limits, loader | PASS | `controller.json`, `safety.json`, `exec-limits.json`, `loader.json` |
| Seal, package_rows, check_queue_rows (entry, limits, worker, report, private plan, pin guard) | PASS | `cpu-seal.json`, `package-rows.json`, `check-queue-rows.json`, `plan-B.log` |
| final_checks / `--ready` | PASS; READY written last; 0 cross-packet mutable pins | `final-checks.json`, `final-pin-guard.json`, `../READY-FOR-DEVICE.json` |

## Record bundle on a chain-rule win (derive from packet190)

A chain-rule win is a screen, not a record. The record needs a fresh-process chain: packet190's harness (packet187's
eleven-window lane-A chain on cards 0+1). Exactly packet190's six changes, re-derived:

1. **Selection.** `k3x-diet` (`eb417ec9…`, 20 keys) replaces packet190's `k3x` (`c5443bbf…`): the one changed key is
   `expert_gateup diet` (the explicit `production` form `c20504b7…` is the same path as the record selection).
2. **Engine.** The packet194 device engine `b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc` (gnu-host twin `5d8f3c057ccbe2214da30bbf98f656f23d63653db328c64102cfdf59425720db`) replaces packet189's
   `87eec645…` (packet190 reused it without relinking).
3. **Memory plan.** Unchanged (`v5/lineage/k3x-diet/memory-plan.json` = packet188/189's k3 ledger, `97a76116…`).
4. **Launcher host floor.** Unchanged: 108,797,048,558 B + 1 GiB.
5. **KD projection.** KD's layer-streaming reference must also project `expert_gateup` to production, with `kernel_io`,
   `rank0_prepare`, `boundary_export`, `rank0_layers`, `boundary` and `snapshot_host`. The diet moves no byte (the k3-state
   canonical identity, the dispatch fixture and the production-shape census).
6. **Bars.** The chain WS128 must beat **62.345282** (packet190) and pass every exactness gate; the chain rule already
   requires ≥ 63.592 in the screen.

Unchanged: the v5 transport size (266,304 B), the oracle binding, the provenance layout, the launcher refusals and the
submission step (coordinator's).

## Notes and limits

* **Not loosened anywhere.** The diet is held to byte identity against the record kernel on CPU (both twins, real rows,
  NaN/Inf strata included) and the row's exactness gates on device; a difference stops the row.
* **The miniature cannot run the diet kernel** (no exp-halfcache layout); its proof covers the key plumbing and the k3
  state. The kernel's engine-level exactness is the dispatch fixture plus the production-shape launch census.
* **The honest risk is the in-engine regime.** packet193 saved 15.9 µs cold / 10.8 µs warm per launch; the engine's
  gate/up launches are between (weights streamed once per layer, inputs L2-warm). Below 11.4 µs the chain bar is missed
  and the screen bar still met; the saving rule at 5 µs kills a gain that the scopes cannot attribute to gate/up.
* **DO-NOT-REPEAT corpus.** All 322 `DO-NOT-REPEAT.md` files under stage2 were grepped (`analysis/dnr-grep.txt`): no row
  closes an exact gate/up instruction diet in the engine or the `expert_gateup` key; packet192/193 carry the diet's premise
  and micro result (pending engine screen). packet189's rows are carried in `DO-NOT-REPEAT.md`.
* **Four kernels in the image, one dispatched.** The pinned header is included whole; the dropped candidates add device
  code but no launch and no allocation (the launch census and the census identity prove both).
