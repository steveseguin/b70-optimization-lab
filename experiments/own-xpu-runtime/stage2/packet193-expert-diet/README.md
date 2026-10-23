# Packet193: exact instruction-diet micro of the record expert kernels (lane-B micro, PROPOSAL ONLY)

CPU preparation is complete; **no GPU ran, nothing is queued, no speed or model-output claim exists.** One proposed
lane-B micro row (`ops/lane-queue/proposed-p193-micro-B.txt`, mirror `proposals/`) measures three exact
instruction-diet candidates against the two record expert kernels, after re-proving byte identity on the device.

## Coordinator ruling (quoted)

> packet192 measured both record expert kernels as instruction-issue bound (no-load within 4 % of L2-warm). Build
> packet193 as the exact instruction-diet micro: candidates `exp-diet` (gate/up), `down-diet` (down) and
> `exp-act-epilogue` (gate/up with the routed-activation epilogue in SLM), each bit-identical to the production kernel
> on all 384 real routes and the NaN/invalid-route fixtures on GNU and Intel host twins before any timing; a candidate
> counts only at <= 0.85x production cold AND warm in both launch orders; one lane-B micro window under 10 minutes.

packet192's bars (`../packet192-expert-issue-floor/evidence/issue-floor-B1/analysis.json`): gate/up cold 73.75 /
warm 46.35 us -> exp-diet bars 62.69 / 39.40; exp-act-epilogue bars 67.29 / 44.01 (kernel + expsact launch);
down cold 45.94 / warm 33.75 -> down-diet bars 39.05 / 28.69. This packet measures its own interleaved controls and
cross-checks them against those datums (kill rule at > 10 %).

## 1. What is built (`p193_diet.hpp` beside the pinned production sources, never edited)

Production, compiled from packet192's pinned closure copied byte for byte (`native-pinned/`, 46 files, absolute includes
rewritten; `p90_expert.hpp` root digest `17c976c4...`, `p100_down.hpp` `329ff3d0...`, re-verified in place against
packet189 and packet103; `native-provenance.json`):

| kernel | class | per launch |
|---|---|---|
| `p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>` | gate/up, 10 routed experts, two streams | 2 x 6,400 rows x K2560, 840-B E1 rows |
| `p100::Kernel<2>` | down tile16 | 25,600 rows x K640, 360-B rows in 16-row tiles |
| `p193diet::ActProduction` | twin of the record's separate `silu_product` launch ("expsact"): `out = bf16(silu(widen(y)) * widen(py))`, `silu(x) = x * (1/(1+detmath::exp(-x)))` (ng::silu, kernels.hpp), after the `!active || error` early return; 50 groups of 128 | 6,400 elements |

Candidates (same WG64 / SG32 / V8 (gate/up) and V16 (down) geometry, same loads and load widths, same per-chain FP32
sequence `v = scale*float(q); product = v*input; sum = sum + product`, no contraction, no reassociation, same outputs,
status, peer_status and error words):

* **exp-diet** (`p193diet::GateUp`, `diet_chains`): (iii) the per-tile `exceptional` test hoisted to one uniform test per
  256-weight step; (i) the sign applied to the decoded weight after the scale multiply; (iv) the four effective scales of
  a step computed once (pure CSE); (ii) byte extraction kept in production's shift/mask spelling (see 2.4).
* **down-diet** (`p193diet::Down`, `diet_tile_chains<false>`): the half -> FP32 scale decode (`iq3::half`, with its
  subnormal loop) once per 32-weight block instead of once per chain (pure CSE); nibble extraction `code&15` / `code>>4`
  per chain parity; the brief's hoisted `d*float(level)` products are a template switch that the ISA gate rejected (2.5).
* **exp-act-epilogue** (`p193diet::GateUpAct`): exp-diet plus the routed activation inside the WG64: sub-group 0 (gate
  stream) writes its eight BF16 gate values to SLM, one local barrier, sub-group 1 (up stream) writes
  `out[logical] = act(gate_bf16, up_bf16)` with the same `act` function as the twin, only when
  `active && !error_at_start && all ten routes valid` (exactly when the separate launch would run: gate/up sets `error`
  for any invalid route before the separate launch starts, and that launch returns on `!active || error`).

## 2. Exact-identity arguments (per candidate; proofs = CPU receipts in `evidence/`)

2.1 **Hoisted `exceptional` (gate/up).** Production tests per tile `(bits(d)&0x7fffffff) >= 0x7f800000 ||
(bits(scale)&0x7fffffff) > 0x7f800000` with `scale = (d*(0.5f+float(sub)))*0.25f`. If `d` is finite, `d*(0.5+sub)` is
finite or +-Inf (both operands finite, `0.5+sub >= 0.5`), never NaN, and `*0.25f` preserves that, so the second clause is
false; if `d` is non-finite the first clause is true. Hence `exceptional <=> d non-finite`, uniform over the step. The
exceptional arm keeps production's `decode_tile` verbatim (NaN/Inf payloads unchanged).

2.2 **Sign after the multiply (gate/up).** Every IQ2_S grid magnitude is in {8, 25, 43} (`p28::iq2_bytes`, 1024 x 8
bytes scanned), so `q != 0` and `float(-q) == -float(q)` exactly; IEEE-754 round-to-nearest multiplication is
sign-symmetric, so `scale*float(-q) == -(scale*float(q))` bit for bit, including `scale = +-0` and `+-Inf`; `scale`
cannot be NaN on the normal arm (2.1). The negation is applied to `v` before the input multiply, so `product = v*input`
and the sum are the production operations on identical operands. (A negation of the *product* would not be exact:
`Inf*0` yields a default NaN whose sign the hardware fixes.)

2.3 **Hoisted scales / half decode (both).** `eff[b][n] = (d*(0.5f+float((scales>>(8b+4n))&15)))*0.25f` is production's
expression with `t.scale = (scales>>(8b))&255` substituted (identical integer, identical float ops); `iq3::half(half)`
and `d*float(level_bank(q))` are pure functions of identical inputs.

2.4 **Byte extraction.** The explicit `std::bit_cast` byte-array form made IGC materialise the array (~10 moves per byte,
`evidence/isa-rejected/first-pass.md`, exp-diet 20.5 instr/weight with 4.9 KB spills); production's `(word >>
(8*j)) & 255` is already lowered to `:ub` byte regions, so the candidates keep that spelling. Item (ii) of the brief is
therefore satisfied by the compiler, not by source changes.

2.5 **down-diet hoisted products rejected.** `lv[q]` with sixteen live products per block lowered to a0 register-indirect
moves (258) plus 512 B of spills at 128 GRF and +26 % dynamic instructions (`evidence/isa-rejected/down-diet-hoisted-products.asm.gz`), confirming the study's register warning; the shipped down-diet keeps production's
per-weight `d*float(level_bank(q))`.

2.6 **Epilogue gating.** `enabled = *active && !error_at_start && routes_valid(all ten)`; `error_at_start` is read before
any write of this launch, `routes_valid` is deterministic for the launch, and `error` is never cleared during it, so the
decision equals the separate launch's `!active || error` test taken after gate/up completed. Proved on CPU by the
`inactive` and `error-preset` strata (production pair vs fused, bytes equal). The partial route (7,3,637) and invalid
expert 512 of packet162b's fixture are exercised (`fixture-f*-invalid`).

2.7 **NaN payload order (receipts, not loosening).** All 3,146 claimed rows are byte-equal on GNU (every stratum, both
kernels, all three candidates, including fixture f2 and the non-finite-scale banks) and the random stress is bit-exact
on both twins in the finite profile (100,000 IQ2 / 200,000 IQ4 blocks) and value-exact in the mixed profile (23,270 /
47,628 exception tiles). On the Intel twin 12 rows of the NaN-producing strata (packet162b's fixture f2 and the
non-finite-scale banks, where every output is NaN) differ in **NaN payload order only**: every differing BF16 word is NaN
on both sides and no status/error byte differs (`evidence/cpu-rehearsal.json: intel.payload_order_rows`); Intel's own
production twin differs from GNU's production fixture the same way (12,800 words on f2). This is the compiler's operand
order of an IEEE add/mul on two NaNs (packet162: "Intel auxiliary NaN chains differ"), outside the engine's admissible
domain (the loader refuses non-finite weight scales; NaN activations are an error state). **Nothing is canonicalised.**
On the device every claimed stratum, including f2 and the non-finite-scale banks, is a strict kill rule (candidate vs
production on the same device); the only diagnostic row is `exp-act-epilogue` on the non-finite-scale bank
(`exactness_claim: false`, 2,334 bytes of NaN payload in `out` on GNU too, all-NaN rows). If the device kills a candidate
for a payload-order-only difference the report says so verbatim; the ruling can then decide.

## 3. ISA gate (`isa_count.py`, offline BMG-G31 via packet81's ocloc pipeline; `evidence/isa.json`, `evidence/isa/*.asm.gz`)

Single-lane walk of the K-loop body (predicated branches fall through; structured `goto` to its UIP; `join` counted),
normalised per weight (64 per gate/up step, 128 per down step). Production gate/up 978 / 64 = **15.28** instr/weight
(the study estimated ~16); production down 2,664 / 128 = **20.81**.

| kernel | static | normal-path dynamic / weight | ratio | goto/join in loop | spills | notes |
|---|---|---|---|---|---|---|
| production gate/up | 1,796 | 15.28 | - | 128 / 128 | 0 | per-weight `exceptional` if/else: 3 control instr per weight |
| **exp-diet** | 2,521 | **11.81** | **0.773** | 130 / 130 (exceptional arm only) | 0 | normal arm straight-line: mov:ub, flag, sel, cvt, mul, shl, mul, add |
| **exp-act-epilogue** | 3,042 | **11.84** | **0.775** | 130 / 130 | 0 | + 3 SLM messages, 1 barrier, 10 route loads per work-item |
| production down | 2,984 | 20.81 | - | 48 / 48 | 0 | `iq3::half` (subnormal loop) 4x per block |
| **down-diet** | 2,751 | **18.50** | **0.889** | 28 / 20 | 0 | half decode once per block |
| act twin | 505 | - | - | 21 / 15 | 0 | 2 mul + 45 mad + 14 madm (detmath exp/div) |

Rejected forms (kept as evidence): bit_cast byte arrays (20.5 / weight, 4.9 KB spills); hoisted down products (spills,
258 indirect movs, 1.26x). Dropped candidates: none; all three reduce the count with zero spills.

## 4. Row (PROPOSAL ONLY)

| lane | card | job | expected | watchdog | device peak | host | writes |
|---|---|---|---|---|---|---|---|
| B | 2 (`0000:43:00.0`) | `packet193-expert-diet-micro-B` | ~137 s (60-411 s) | 1,800 s | 1,119,693,652 B (< 1.2 GB) | 10 GiB available | 96 MiB |

Per candidate, in the window, BEFORE timing: byte identity on the device of production vs the host fixtures and of the
candidate vs production (all 384 real routes, warm, packet162b real rows, f0/f1/f2 x valid/invalid, non-finite-scale
bank, epilogue inactive/error-preset). Then timing with production and candidate interleaved: cold = 384 routes, 512 MiB
scrub before every launch, 20 repeats, pass 0 order A/B and pass 1 order B/A (30,720 scrub+launch cycles = 28.4 s per
candidate at packet100b's 0.92 ms/cycle); warm = route 0's experts, 5 warm-ups + 200 repeats per order; gate/up candidates
also packet162b's real layer0/layer24 rows. The epilogue's production arm is gate/up followed by the act twin (event
times summed; the inter-launch gap reported). Duration: 3 x 28.4 s cold + ~1 s warm each + exactness ~12 s + 1.0 GB bank
generation/upload ~22 s + JIT ~15 s = ~137 s. Device memory phased (gate/up then down); no model load.

## 5. Report (`s193_report.py` -> `evidence/diet-B1/analysis.json`, `s193_report.md`)

Per candidate and stratum: production and candidate medians (p10/p90) per order, ratios A/B and B/A, the <= 0.85
verdict per stratum; per candidate: qualified / closed / withheld, us per layer-equivalent saved (cold), projected
record-line gains (two cards: +1.32 % per 0.01 ms per GDN layer; one card: 11.4 us/layer = +2 %), combined projection
(best gate/up pick + down-diet). Kill rules: any byte difference in a claimed stratum on the device withholds that
candidate (the kill names "value difference" or "NaN payload order only"); production cold/warm disagreement with
packet192 > 10 % and any stratum p90/median > 1.5 withhold the whole verdict. The analyzer refuses CPU streams and
packet192's stream, and its control constants are tested against packet192's REAL `analysis.json` (`test_report.py`,
8 tests).

## 6. Gates (all CPU, in order; `nice -n 19 taskset -c 8-15,24-31 python3 -B <script> </dev/null`)

1. `prepare_native.py` 2. `build_micro.py` (three binaries, 0 warnings, closure inside the packet) 3. `prepare_inputs.py`
4. `isa_count.py` (offline ISA; every candidate must reduce the count with no spills) 5. `rehearse_cpu.py` (host twins
at production shape, fixtures, stress, 9 sandboxed probe/refusal cases with the real argv) 6. `test_report.py`
7. `admission.py` 8. `package_rows.py` (proposal + seal) 9. `check_queue_rows.py` (real `run_micro.py --plan`,
private-copy `lanequeue.py plan --lane B`, shared `rehearse_entry --report`, live pin guard) 10. `final_checks.py --ready`
(READY-FOR-DEVICE.json written LAST; 0 cross-packet mutable pins).

Units were polled before every compile (`units_idle`, which would also tolerate the owner's endpoint-restore window
`window-p192-driver ...-restore18` named by the brief): that window had already finished, and every compile and the ISA
pipeline saw no active window/lanequeue/packet unit (`evidence/build.json: records[].units`, `evidence/isa.json: units`). Parent files are read in place and verified by digest (`lineage-inputs/parent-inputs.json`). See
`DO-NOT-REPEAT.md`, `RETENTION.md`, `notes/2026-10-23-packet193-expert-diet.md`.
