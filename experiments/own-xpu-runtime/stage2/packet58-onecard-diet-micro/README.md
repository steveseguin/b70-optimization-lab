# Packet58-onecard-diet-micro: exact instruction-diet micro of the ONE-card record gate/up kernel (lane-B micro, PROPOSAL ONLY)

**Status (2026-10-23, CPU only): preparation complete; no GPU ran, nothing is queued, no speed or model-output claim
exists.** One proposed lane-B micro row (`ops/lane-queue/proposed-p58-dietmicro-micro-B.txt`, mirror `proposals/`)
measures one exact instruction-diet candidate, `p58-diet` (`p58ag_diet::GateUp`), against the one-card record line's
gate/up kernel `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached=true>` after re-proving byte identity on the device.
This is the micro that packet58-onecard-diet's STOP report asked for (its "recommendation 1"); the engine key
`expert_gateup=production|diet` and the one-card screen (recommendation 2) come after a PASS here.

Line: Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS, own Xe runtime, one B70, selection `experts=wide64+halfcache`, record
36.602512 tok/s (packet58-onecard-cache23-chain, engine `083e3853...`, LocalMaxxing `cmvkcqznb002lng01fsrhjn7t`).

## Coordinator ruling (quoted)

> "packet58-onecard-diet found the one-card gate/up kernel is `p58ag_exp` (halfcache, 820 B rows, table decode,
> indirect slots), not `p90exp`. Derive the one-card diet as a packet193-shaped micro: apply the same three exact
> transformations to `p58ag_exp::wide_chains` keeping the halfcache table decode and the slot resolution unchanged,
> prove bit-identity on CPU on halfcache and indirect-slot strata with GNU and Intel host twins, count the ISA, and
> measure cold / warm against the production one-card kernel in both orders on one lane-B micro row under 10 minutes;
> a candidate counts only at ≤ 0.85× production cold AND warm."

## 1. What is built (`p58ag_diet.hpp` beside the pinned production source, never edited)

Production is compiled from a byte-for-byte copy of the record line's generated header
`packet58-onecard-cache23/native/generated/p58ag_expert.hpp` (sha `89394237...`, identical to the compiled
`build/native/` copy) and the transitive closure of its absolute includes out of that packet's frozen one-card tree
(`native-pinned/`, 44 files; 43 verified against `packet58-onecard-cache23/lineage/path-rewrite.json`; only the
absolute include/`#line` prefixes are rewritten so each header has one `#pragma once` identity; provenance in
`native-provenance.json`). The record's device compile flags are used (`lineage/58ag-build-commands.json`:
`-std=gnu++20 -O2 -fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee -foffload-fp32-prec-div
-foffload-fp32-prec-sqrt -fsycl`).

| kernel | per launch | row format | scale decode | row address |
|---|---|---|---|---|
| production `p58ag_exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true,0,Cached=true>` | 2 streams × 6,400 rows × K2560, 10 routed experts | 820-B `p49bgemv::layout(IQ2_S,2560)` rows (codes 0..639, high 640, scales 720, halves 800) | 16-bit half at `halves+2*step`, `halfcache[bits]` (65,536-entry FP32 table, binding `p[19]`, filled with `iq3::half(i)`) | `p58::resolve(bank, source*rb, rows*rb, indirect)` over `p58::Pointer{address,generation}` slots; **`indirect=true` on the record line** (`main.cpp`: `b.indirect=caching()&&op=="expert_gate_up"`) |
| candidate `p58ag_diet::GateUp` | identical | identical | **identical line kept verbatim** | **identical, `p58::resolve` unchanged**; binds through the production `Kernel::bind` (20 slots incl. `p[19]`) |

The candidate is `diet_chains`: packet193's three exact transformations applied to `p58ag_exp::wide_chains<IQ2_S,K,8>`
with the same WG64 / SG32 / V8 geometry, the same loads and load widths (codes vec4, 16-bit high/scales, one 16-bit
half + one table gather per 256-weight step) and, per chain, the identical FP32 sequence `v = scale*float(q);
product = v*input; sum = sum + product` for j = 0..7 in order (no contraction, no reassociation). The kernel shell
(logical_row, the `P`-lane select tree, the status/error epilogue, `ownrt::prepared_submit`, no `packet26::checked`,
as production) is production's text with `chains` replaced. The micro also calls the production dispatch's boundary
validation `p39::validate<IQ2_S,2560,expert_checks,1>` on every binding it launches (rb = 820, indirect extents
`experts*sizeof(Pointer)`, the halfcache binding and alias checks are the dispatch's, untouched).

## 2. Exact-identity arguments, re-checked against THIS kernel's code

The production decode is `p58ag_exp::decode_tile` (textually `p90exp::decode_tile`) applied per tile to
`d = halfcache ? halfcache[bits] : iq3::half(bits)`. Three questions the brief asked, answered from the source:

* **Where does the sign come from in the half decode; does the table carry it?** The weight sign is the sign BYTE of
  the 16-bit code pair (`signs = t.a >> 8`, one bit per weight) and is applied in `decode_tile`; the table carries only
  `d` (the block scale as an FP32, including the half's own sign bit through `iq3::half`). The diet does not touch the
  table or `d`; it changes only where the per-weight sign bit is applied. So "the table already carries the sign" is
  false for the weight sign and irrelevant for the block sign (which stays inside `scale`).
* **Is `exceptional ⇔ d non-finite` still true?** Yes, and more strongly than on the two-card kernel: `d` is a table
  entry `iq3::half(bits)` = finite with |d| ≤ 65504, or ±Inf, or the canonical NaN (`math.hpp`: e==31 →
  `sign|0x7f800000|(m?0x400000:0)`). `scale = (d*(0.5f+float(sub)))*0.25f` with `0.5 ≤ 0.5+sub ≤ 15.5`: `d` finite
  ⇒ |d*(0.5+sub)| < 2^20, finite (never even ±Inf), `*0.25f` finite ⇒ the second clause
  `(bits(scale)&0x7fffffff) > 0x7f800000` is false; `d` non-finite ⇒ the first clause is true. Hence
  `exceptional ⇔ d non-finite`, uniform over the step. (For an arbitrary FP32 table entry packet193's weaker argument
  still holds: `d` finite ⇒ `d*(0.5+sub)` finite or ±Inf, never NaN.) `halfcache == nullptr` (`Cached=false`) falls
  back to `iq3::half(bits)` on the same line in both kernels.
* **Is the accumulation order preserved?** Per chain the eight products and sums are the same operations on the same
  operands in the same order (`accumulate` is production's loop); chains are independent partial sums (`sums[chain]`)
  combined by the untouched `local_tree` and the `P`-lane select tree. The exceptional arm is production's
  `decode_tile` verbatim per tile, so NaN/Inf payloads follow production's operation order.

2.1 **Hoisted `exceptional` (iii)**: see above; one uniform test per step on `d`.

2.2 **Sign after the multiply (i)**: every IQ2_S grid magnitude is in {8, 25, 43} — proved at compile time against THIS
tree's table (`static_assert(grid_magnitudes_in_8_25_43())` scans all 1024 × 8 bytes of `p42expert::iq2_words`), so
`q ≠ 0` and `float(-q) == -float(q)`; IEEE-754 round-to-nearest multiplication is sign-symmetric, so
`scale*(-float(q)) == -(scale*float(q))` bit for bit, including `scale = ±0` (a ±0 half) and every finite scale;
`scale` is never NaN or Inf on the normal arm (2.1). The negation is applied to `v` before the input multiply, so
`product = v*input` and the sum are production's operations on identical operands. A negation of the product would not
be exact (`Inf*0` default-NaN sign); it is not used.

2.3 **Hoisted effective scales (iv)**: with `k = first+chain*8`, `i = k%256 = 8*(physical*8+chain)`: `q%4 == chain%4`,
`(i/16)%2 == (chain/2)%2`, scale byte = high byte = `chain/4` (compile-time after unrolling), so
`eff[b][n] = (d*(0.5f+float((scales>>(8b+4n))&15)))*0.25f` is production's expression with
`t.scale = (scales>>(8b))&255` substituted: identical integer, identical float ops, computed once per step (CSE).

2.4 **Dropped: nothing.** All three transformations are provably bit-exact on this kernel. Byte extraction keeps
production's shift/mask spelling (packet193's ISA gate rejected `std::bit_cast` byte arrays); the table gather, the
slot resolution, the bindings and `p39::validate` are unchanged.

2.5 **NaN payload order (receipts, not loosening).** The GNU twin is bit-exact everywhere, NaN payloads included
(1,250 byte rows equal; the 100,000-block mixed stress 0 mismatches). The Intel twin differs from the GNU fixtures and
from its own production on the NaN-only strata (packet162b's NaN-input fixture f2, the non-finite-half bank) in NaN
payload order only (every differing BF16 word is NaN on both sides, 0 status/error bytes), and the first Intel build's mixed
stress had 128,314 production-vs-candidate chain differences, all NaN-vs-NaN (0 value); the rebuilt twin (the stress
row now classifies the table-vs-computed comparison too) is 0 everywhere. This is the compiler's operand order of an
IEEE add/mul on two NaNs (packet162/193), outside the engine's admissible domain (the loader refuses non-finite weight
scales). Nothing is canonicalised. Those strata are therefore labelled `nan_claim` and compared **by is-NaN per word**
everywhere (host twins and device): a payload-order-only difference is recorded, never a kill; a value difference or a
status/error byte there is a kill. This is packet193's lesson (its window stopped on the production kernel's device
NaN order vs the host fixture), applied by construction.

## 3. ISA gate (`isa_count.py`, offline BMG-G31 via packet81's ocloc pipeline; `evidence/isa.json`, `evidence/isa/*.asm.gz`)

Single-lane walk of the K-loop body (packet193's method, unchanged), normalised per weight (64 per step).

| kernel | static | normal-path dynamic / weight | ratio | goto/join in loop | spills | GRF | notes |
|---|---|---|---|---|---|---|---|
| production `p58ag_exp` | 2,058 | **15.66** | - | 134 / 132 | 0 | 128 | per-weight `exceptional` if/else; the per-step table gather costs ~0.4 over the two-card kernel's 15.28 |
| **`p58-diet`** | 2,151 | **12.02** | **0.767** | 8 / 6 | 0 | 128 | normal arm straight-line; walked float-mul count 136 = production's (consistency check) |

The candidate reduces the count with zero spills and is admitted to the window. (packet193's two-card exp-diet:
15.28 → 11.81, ratio 0.773; device 0.784× cold / 0.77× warm; provenance only.)

## 4. Row (PROPOSAL ONLY)

| lane | card | job | expected | watchdog | device peak | host | writes |
|---|---|---|---|---|---|---|---|
| B | 2 (`0000:43:00.0`) | `packet58-onecard-diet-micro-B` | ~68 s ([60, 202] s) | 1,800 s | 1,106,093,204 B (< 1.2 GB) | 10 GiB available | 96 MiB |

In the window, BEFORE timing: device byte identity of production vs the GNU host fixtures and of the candidate vs
production and vs the fixtures on every stratum: `cold` (all 384 packet100b routes, indirect identity slots = the record
line's path), `warm` (route 0, indirect), `warm-direct` (route 0, `indirect=false`; also production direct vs indirect),
`slots-reverse` / `slots-shuffled` (8 routes each over non-identity slot tables, cross-checked against production run
directly on the permuted routes), `warm-real-layer0` / `warm-real-layer24` (packet162b's real GGUF rows re-laid out into
the 820-B layout by the line's own `p49bgemv::repack_row`, 10-expert slot tables), `fixture-f0/f1 × valid/invalid`
(invalid expert 512 and the partial route (7,3,637)); NaN-only strata `fixture-f2 × valid/invalid` and `exceptional`
(the non-finite-half bank: ±Inf, quiet/signalling NaN patterns, ±0, half subnormals, max finite) by is-NaN per word.
Then timing, production and candidate interleaved: cold = 384 routes, 512 MiB scrub before every launch, 20 repeats,
pass 0 order A/B and pass 1 order B/A (30,720 scrub+launch cycles ≈ 28 s at packet100b's 0.92 ms/cycle); warm = route 0
(indirect), warm-direct, and the two real-row shapes, 5 warm-ups + 200 repeats per order; then a **fresh production-only
control pass** (cold 384 × 20 with scrub, warm 205; order `P`) for the 10 % control rule. No model load; one phase.

## 5. Report (`s58dm_report.py` → `evidence/dietmicro-B1/analysis.json`, `s58dm_report.md`)

Per stratum: production and candidate medians (p10/p90) per order, ratios A/B and B/A, the ≤ 0.85 verdict; the gate
strata are `cold` and `warm` (both orders); `warm-direct` and the real-row strata are reported, not gated. µs per layer
saved (cold and warm) and the one-card projection at the ruling's 11.4 µs/layer = +2 % (48 serial layer bodies). Kill
rules (never ratio-corrected): any byte difference on a claimed stratum (value difference) withholds the candidate; a
NaN-payload-order-only difference on a NaN-only stratum is recorded, never a kill; production cold/warm disagreement
with the fresh production-only pass > 10 % and any stratum p90/median > 1.5 withhold the whole verdict. The analyzer
refuses CPU streams and packet193's real two-card stream, and packet193's REAL NaN-payload row (2,353 NaN-vs-NaN words,
0 other bytes) replayed into this schema is accepted as diagnostic by both the analyzer and the wrapper's in-window gate
(`test_report.py`, 9 tests on the real `samples.jsonl`). The wrapper releases the lane (`drain.complete`,
`lease.complete`) BEFORE the exactness gate and the report; a post-drain failure writes `report-failure.json` and exits
1 cleanly, and a surviving self-owned `active-lane-B.json` is archived into the evidence and removed (packet193's
window left its marker with a dead owner).

## 6. Gates (all CPU, in order; `nice -n 19 taskset -c 8-15,24-31 python3 -B <script> </dev/null`)

1. `prepare_native.py` 2. `build_micro.py` (three binaries, 0 warnings, closure inside the packet) 3. `prepare_inputs.py`
4. `isa_count.py` 5. `rehearse_cpu.py` (host twins at production shape with the table and the slot tables, fixtures,
100,000-block stress per profile, 9 sandboxed probe/refusal cases with the real argv) 6. `test_report.py`
7. `admission.py` 8. `package_rows.py` (proposal + seal) 9. `check_queue_rows.py` (real `run_micro.py --plan`,
private-copy `lanequeue.py plan --lane B`, shared `rehearse_entry --report`, live pin guard) 10. `final_checks.py
--ready` (READY-FOR-DEVICE.json written LAST; 0 cross-packet mutable pins).

Units and other host compilers (by exact `comm`, never `pgrep -f`) were polled before every compile
(`evidence/build.json: records[].units`, `evidence/isa.json: units`); the coordinator's compile hold for the packet195
chain (06:4x UTC) was honoured: the host-twin rebuild for the stress classification waited for clearance. Parent files
are read in place and verified by digest (`lineage-inputs/parent-inputs.json`, `native-provenance.json`). Binaries:
`evidence/build.json` (device `9b7bf47e066a40932d3908d99230a7252cd83333383ad0fe8916e9e4f4e0c641`, GNU twin `730e2bcc60ea52eb3a162dacc02f49cbbae936d307fe795e26528e11b2a0a2fe`, Intel twin `51d5bf8b9620889ee492afb91769f3f6983931c7991fa116c7817173bb007748`). See `DO-NOT-REPEAT.md`,
`RETENTION.md`, `notes/2026-10-23-packet58-onecard-diet-micro.md`.
