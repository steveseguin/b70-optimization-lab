# Packet194 negative-result index (exp-diet gate/up kernel in the k3x record engine, `expert_gateup=production|diet`)

No device result exists yet. After the window, append the row from row 1's `bracket-summary.json` → `s194_decision` (or
`python3 -B v5/s194_decision.py <rows 0..1>`).

## Ruling (coordinator, 2026-10-23, quoted)

"packet193 measured the exact gate/up instruction diet at 0.78× production cold and 0.77× warm on card 2, byte-identical on
every claimed stratum. Integrate `exp-diet` into the k3x record engine as an in-load key `expert_gateup=production|diet`
(production = byte-for-byte the record kernel), prove engine-level exactness on CPU, and screen it on lane B with a one-load
bracket k3x / k3x+diet / k3x / k3x+diet / k3x. Screen winner at ≥ +0.5 % over every k3x view; chain rule at ≥ +2 % over every
k3x view AND ≥ 63.592 tok/s. Kill rules: any inexact view; proposals or acceptance differ; k3x drift > 0.5 %; the diet's
per-layer gate/up saving (from the p150 scopes or the class attribution of packet191 if cheap) < 5 µs."

## Rows checked before work (quoted; packet189's rows carried, plus the diet search)

* **All 322 DO-NOT-REPEAT.md files under stage2** were grepped (`analysis/dnr-grep.txt`) for `expert_gateup`, `exp-diet`,
  `instruction diet`, `p193diet`, `GateUp`, `gate/up diet`, `sign after`, `hoisted exceptional`: only packet192 (the
  issue-floor premise) and packet193 (the micro, "PASS → packet194 engine screen") mention the mechanism; no row closes it.
* **packet193 (2026-10-23).** Closed by its ISA gate: `std::bit_cast` byte-array extraction (IGC materialises the array) and the
  hoisted down products (spills); closed on device: down-diet (0.96, below the 0.85 bar) and exp-act-epilogue (0.82/0.85, no
  gain over exp-diet + the separate activation launch). **Only exp-diet enters the engine.** NaN payload order is never
  canonicalised (the device gate stays strict; the packet193 stop was the production kernel vs a host fixture, diagnostic).
* **packet192 (2026-10-23).** Both record expert kernels are instruction-issue bound (gate/up cold 73.75 / warm 46.35 /
  no-load 44.69 µs): the premise, never a speed claim.
* **packet189 rows (carried).** "Do not run layer 26 (or 24-25) inside a speculative half, or before the accept." "Do not
  add QSA layer 23 or 27 to the boundary." "Do not route a device→host readback of more than a few hundred bytes through
  the KioCopy kernel." "Do not read the boundary-vs-draft rule from the op-9 duration." "Do not compare the bracket's V3
  views with the record without a fresh V3 load." "Do not start a record chain below the chain rule, and do not submit a
  screen." All hold: the k3x views ARE the record selection's engine path (the full-shape gate proves the 20-key `k3x` captures
  equal the 19-key record selection's), so no fresh reference row is needed; D stays the draft wall; the export stays on the
  copy engine; the diet is a kernel choice with 0 B of allocation.
* **packet188 (closed).** The kio-export composite as built (−0.26 %): not touched; `boundary_export=kernel` is not re-measured.
* **Expert-class closures carried from packet193's index** (geometry sweeps, prefetch/halfcache variants, grid relocation,
  2D block loads, large GRF, kernel-order layout, enumerative decoders, warm-ahead): none is re-tried; the diet is an
  instruction-count change of the record kernel with identical loads.
* **Harness lesson (memory: "an arm that matches baseline exactly is inert, not neutral").** The engine refuses
  `expert_gateup=diet` with a non-halfcache `experts` choice outside the miniature, counts the diet sites and the
  other-layout (IQ3_S p28) gate/up sites per prepare, refuses a selected diet with zero diet sites at production shape, and
  the production-shape gate requires the diet kernel at every exp-halfcache gate/up site, so a silently inert candidate
  cannot reach the device.

## Measured (closed)

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | **packet189 k3x on the V3 record line** (packet188's k3 + trims with the boundary export on the copy engine) | **WIN, chain rule met**: one load V3/k3x/V3/k3x/V3 = 60.615/**62.242**/60.444/**62.225**/60.498 (+2.66 % over the fastest V3 view, every view 13/13 exact); record bundle packet190: fresh chain **62.345282** tok/s, LocalMaxxing `cmvk51wfn001gng01fpbfy89q` | — (it is the current record line) |
| 2026-10-23 | **packet193 exp-diet micro** (card 2) | gate/up cold 57.92 vs 73.85 µs (0.784), warm 36.0–36.2 vs 46.77 (0.77); byte-identical on every claimed stratum | — (this packet is its engine screen) |

## Pending (this packet)

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-23 | **exp-diet in the k3x record engine** (`expert_gateup=diet`, selection `k3x-diet` eb417ec9…, engine packet194): rows k3x-diet smoke, one-load k3x/k3x-diet/k3x/k3x-diet/k3x (lane B); decision `s194_decision`; priced +1.4 % (10.8 µs warm) to +2.1 % (15.9 µs cold) at +1.32 % per 0.01 ms per GDN layer | **pending device measurement** | — |

## Boundaries (do not)

* **Do not loosen exactness for the diet.** It is byte-identical to the record kernel on CPU (both twins, real rows, NaN/Inf
  strata) and on packet193's device run; any device difference in the screen stops the row and is reported verbatim.
* **Do not screen the diet on a non-halfcache gate/up layout.** The diet is a diet of `p90exp::Kernel<IQ2_S,2560,64,wide>`
  only; the engine refuses it elsewhere.
* **Do not treat the miniature's canonical identity as the kernel proof.** The miniature has no exp-halfcache layout (diet
  inert, counted); the kernel proof is `diet-fixture.json` + the production-shape launch census.
* **Do not read a gain without the per-layer saving.** The 5 µs rule attributes the gain to gate/up on both ranks from the
  host scopes; a gain the scopes cannot see is not the diet's.
* **Do not start a record chain below the chain rule, and do not submit a screen.** A record is a fresh chain from packet190
  with the k3x-diet selection and this engine, WS128 above 62.345282, exact.
