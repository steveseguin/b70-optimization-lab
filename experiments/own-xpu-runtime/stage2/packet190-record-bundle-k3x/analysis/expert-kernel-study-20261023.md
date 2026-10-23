# Expert GEMV kernel: distance from the copy floor and go/no-go on a micro packet (2026-10-23, CPU-only)

Scope: Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, B70. Records: two cards 62.345 tok/s (packet190 k3x), one card
36.603 (packet58-onecard-cache23). Nothing was built, run on a device, queued or written into the repo; every number is
read from the ledger and the file it came from is named. Arithmetic: `expert_kernel_arith.py` beside this file.

## 0. Three corrections to the brief, from the sources

1. **The routed experts are not IQ3_XXS.** The record kernels are instantiated only for `IQ2_S, K=2560` (gate/up) and
   `IQ4_NL, K=640` (down): `packet103-record-bundle/p49d_expert_submit.cpp` lines 36-37 (`m[0].type==Type::IQ2_S&&m[0].columns==2560`,
   `Type::IQ4_NL&&m[0].columns==640`), `p90_expert.hpp` (`static_assert(T==Type::IQ2_S)`), `p100_down.hpp` (`T=IQ4_NL,K=640`).
   `roofline.json` tensors confirm: `blk.3.ffn_gate_exps.weight IQ2_S [2560,640,512]`, `ffn_down_exps.weight IQ4_NL [640,2560,512]`.
   The K2 registry has `expsgate.iq2` for 47 layers and `expsgate.iq3` (IQ3_S) for 1 layer; the IQ3_S layer goes through the
   generic p28 path and is not the lever. IQ2_S = 82 B per 256 weights (2.5625 bpw: 8-bit grid index + 8 sign bits per 8
   weights, 2 high index bits per 8 weights, 4-bit sub-scale per 16 weights, FP16 block scale); the 1,024-entry
   grid (8 KiB, magnitudes 8/25/43) is global constant data read with one `load.ugm.d32x2` per 8 weights. IQ4_NL = 18 B per
   32 weights (16 nibbles into a 16-level table held in immediate register banks, FP16 scale).
2. **The record's expert kernels are NOT the K2 `expsgate`/`expsdown` table entries.** The k3x selection
   (`packet189-twocard-k3x/v5/lineage/k3x/selection.json`) has `"experts": "exp-halfcache+down-tile16"`, which
   `p49d_expert_submit.cpp::expert(choice)` resolves to arm 10 = `p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>`
   (packet65 wide64 geometry + packet90 E1 FP32-cached block scale, 840-B rows) and arm 21 = `p100::Kernel<2>` (tile16
   down: 16-row transposed 360-B rows, `p65::wide_chains` arithmetic). The packet190 K2 receipts
   (`build/device-cards01-p190-a/K2/run0/summary-k2-measured.json`) time the dispatch-table kernels `p28.paired.wg32`
   (82.4 us) and `p33.down.bank` (120.3 us); those are the older kernels behind the `gemv` table and are not launched for
   the routed experts (packet65: "The production call is `p49d::expert`, not the older kernel suggested by the inherited
   dispatch label"). The one-card record uses the same pair (`--experts wide64+halfcache` + down-tile16; one-card synthesis 1
   "dispatch identical").
3. **Floor 37, excess 74 -- not floor 74, excess 31.** `packet110-class-roofline/roofline.json`: expsgate floor 20.08 us,
   expsdown floor 17.28 us, sum **37.4 us/layer**; measured 60.4 + 50.9 = 111.3; lever synthesis 4 wrote "111 us (excess over
   the 537 GB/s copy floor 74 us)" and packet191's analysis.json carries `experts excess 79.7 over floor 36.96`. The brief's
   "copy floor 74 (excess ~31)" swapped the two. Everything below uses floor 37.4.

Hardware model used (ledger values, not the brief's 20 x 8 x 8): `packet7-kopt2/analysis.json` reports
`max_compute_units: 256` (256 XVEs = 32 Xe cores; the offline compiles target BMG-G31), 8 threads per XVE (packet115:
large-GRF "halving resident threads per core"), so **2,048 resident SIMD32 subgroups**; clock 2.8 GHz (xpu-smi in the
Qwen notes); L2 25,165,824 B (packet119 runtime-reported global cache); copy roofline 537-555 GB/s.

## A. Distance from the copy floor

### Shapes and bytes per layer per token (both ranks run the same kernels; a layer runs on exactly one rank)

| Projection | rows x cols per expert | row bytes | routed rows | weights | bytes read |
|---|---|---|---|---|---|
| gate + up (IQ2_S, E1 840-B rows) | 640 x 2560, x2 streams | 840 (packed 820) | 2 x 6,400 | 32,768,000 | **10,752,000** (packed 10,496,000) |
| down (IQ4_NL, tile16) | 2560 x 640 | 360 | 25,600 | 16,384,000 | **9,216,000** |
| activations/outputs | x 5,120 B; down x 12,800 B; y/py 25,600 B; down y 51,200 B | | | | ~95 KB |

Copy floor: gate/up **20.08 us** @537 (19.43 @555); down **17.28** (16.72); class **37.4** (36.2). The floor is a
read-roofline reference; packet140 row 3 ("packet110 is not an attainable floor") and packet110's own text say the gap is an
opportunity budget, never a realizable saving.

### Measured (us per call)

| Source | gate/up | down | act | note |
|---|---|---|---|---|
| packet110 roofline.json, synthetic complete layer, 10-18 selection (E1 halfcache, pre-tile16 down) | 60.37 (QSA 59.0) | 50.89 | 5.42 | 2 owners x 40 calls |
| packet77 raw events (packet81 ANALYSIS.md) | 61.5 / 62.1 | 52.2 / 52.6 | | rank0 / rank1 |
| packet86 production rank1, ms/half / 24 | 62.3 | 50.3 | | packet84 selection |
| packet100 tile16 down micro, 384 real routes, 512 MiB scrub | | 0.695 x production | | +2.09% / +1.68% in engine |
| **packet162b production gate/up on a 10-expert compact bank (10.75 MB <= L2), 200 A/B pairs** | **48.3** | | | `evidence/enum11-diagnostic-B1/analysis.json` |
| packet191 sampled sites on the record line (recorder ~32 us/layer spread over classes) | class 105 incl. act | | | table withheld (completeness rule) |
| packet86 ablations rank1 (non-exact): exp-nodeq 33.8, exp-constgrid 38.5, exp-loadkeep 65.5; down exp-onecached 35.4 | | | | bounds, non-additive |

Record-line estimate per layer: gate/up 60.4 + down(tile16) ~35.4 + act 5.4 = **~101 us** (packet191 sampled 105 with the
recorder share), i.e. **excess ~64 us/layer over the 37.4 floor**: gate/up 40 us over its floor, down ~18, act 5.

### Which bound binds (from the kernel source + linked assembly)

Geometry (`p90_expert.hpp`, `p65_expert.hpp::wide_chains`, `p100_down.hpp`): both kernels use WG64 = 2 x SG32, `reqd_sub_group_size(32)`.
Gate/up: subgroup 0 = gate stream, subgroup 1 = up stream of the same 8 rows; V = 8 rows per subgroup, P = 32/V = 4 physical
lanes per row, each lane owns 8 interleaved logical chains (k = step*256 + 8*(lane*8+chain)); 10 steps of 256. 6,400 rows / 8
= **800 WGs = 1,600 SGs = 78% of the 2,048 slots: one wave, 6.25 SG per XVE**, no second wave to hide the tail. Down: V = 16,
P = 2, 25,600 rows / 32 per WG = 800 WGs = 1,600 SGs, same 78%. Per gate lane per step: one `d32x4` code load (16 B), two
`d16` (high, sub-scales), one `d32` FP32 scale (E1), then per 8-weight tile one dependent `d32x2` grid read and the 8 BF16
inputs as four scalar `d32` loads (packet81: "32 activation loads per loop"); 128 configured GRFs, zero spills (packet65/81
register reports).

Instruction inventory, linked BMG assembly of the production pair (`packet81-experts3/evidence/instruction-mix.json`,
opcode histogram of `registers-production/kernel-1.asm.gz` / `kernel-3.asm.gz` done here):

| | gate/up (IQ2_S) | down (IQ4_NL) |
|---|---|---|
| static instructions / loads | 1,993 / 51 | 2,955 / 79 |
| loop body static ALU per weight (incl. exceptional path) | 21.9 (849 int + 554 fp per 64 weights) | 19.5 (1912 int + 584 fp per 128) |
| opcode mix (whole kernel) | mov 538, mul 292, and 189, add 186, goto 163, join 158, sel 142, shl 117, cmp 47, shr 29 | mov 626, and 421, mul 277, add 272, sel 269, shr 257, shl 214, cmp 162, bfn 152, goto 60, join 55 |
| normal-path dynamic estimate | ~16 / weight | ~15 / weight |

Per weight the exact identity itself costs three FP32 ops that cannot be fused or reordered (`v = scale*float(q)`,
`product = v*input`, `sum = sum+product`, FP contraction off), plus integer decode: magnitude extract (shr, and), sign
(shr, and, neg, sel), int->float cvt (a `mov`), input BF16->FP32 (shl), and per 8-weight tile the structured `exceptional`
branch (goto/join pairs: 163/158 static in gate/up). Essential minimum for an exact kernel is ~9-10 instructions per weight.

Issue model (256 XVE, SIMD32 instruction = 2 clocks on the SIMD16 datapath, 2.8 GHz):

| | gate/up | down |
|---|---|---|
| issue time at the current ~16 / ~15 instr/weight | **45.7 us** (22.9 if 1 clk) | 21.4 us (10.7) |
| copy-floor budget | 14.1 XVE-cycles per 32 weights = **7.0 instr/weight** | 24.2 cycles = 12.1 instr/weight |
| ALU floor of an exact kernel at 9.5 instr/weight | **27.1 us** | 13.6 us |

Verdict per kernel:

* **Gate/up is instruction-issue / dependency-bound, not bandwidth-bound.** With the whole working set in L2 (packet162b)
  it still takes 48.3 us = 2.4x its copy floor, within 6% of the pure issue time at ~16 instr/weight x 2 clk. DRAM adds only
  ~12 us (60.4 engine - 48.3 warm). The packet86 ablations agree: with every load kept and all decode removed (`exp-nodeq`)
  the kernel still takes 33.8 us > the 20.1 us floor (the load/issue skeleton alone is 1.7x the floor); the decode costs
  ~27 us of which the dependent grid stage is ~24-27 us (`loadkeep - constgrid`). Occupancy is 78% of slots in a single wave
  with 6.25 threads/XVE, so dependent-load latency is only partly hidden -- packet115 (half the threads -> 1.44x slower) and
  packet81 (loads 51->27 neutral) both point at latency/issue rather than DRAM. The ALU floor of an exact kernel (~27 us) is
  *above* the copy floor (20 us): even a perfect exact kernel cannot reach the copy floor on this format.
* **Down is mixed: ~21 us of issue plus ~15 us of memory/latency** (engine ~35 after tile16; floor 17.3). tile16 (a pure
  byte permutation) took 0.695x in the micro and +2% in the engine, so its memory pattern mattered; its issue floor at
  ~15 instr/weight (21 us) now sits above its copy floor.
* **Act** (5.4 us) is a separate launch (`Kind::expert_checks` is used for gate/up, not `Kind::expert_act`; `expsact` is its
  own class in packet110/191) because the split-stream design puts gate and up in different subgroups.

So the ~64 us/layer excess decomposes roughly as: gate/up issue+dependency ~28 (warm) + DRAM ~12; down issue ~4 over floor
+ memory ~14; act 5. The kernel is "ALU-bound" in the brief's sense (dequant + the exact 3-op chain), with latency on top.

## B. Mechanisms: closed vs open (DO-NOT-REPEAT corpus, 261 files grepped; rows quoted from the packets named)

| Mechanism | Ledger status | Evidence / row | Ceiling if open |
|---|---|---|---|
| (i) pre-expanded 8-bit magnitude stream once per load | **net loss by bytes**: 1 B/weight -> gate/up 32.8 MB -> copy floor 61 us > current 60. packet162: "Full byte ... expansion extra 33.97 GB per rank exceeds rank-1 786 MB headroom" | packet162 DNR | none |
| (i') pre-expanded 2-bit magnitude + sign stream (3 bits/weight, drops the grid lookup) | **closed by memory**: 108-B blocks = 1,080-B rows, +28.6% = **+3.77 GB per rank** vs 630 MB rank-1 headroom (packet162 "two-bit expansion +3.77 GB"); on one card +28.6% miss bytes (= -1.2% from the 1.0-1.5 ms miss term) | packet162 DNR; packet191 memory census | copy floor +5.7 us; removes the ~24 us dependent stage -> would be +15-18 us if it fit; it does not |
| grid table relocation/compaction (SLM, compact global) | closed: 1.24-1.78x slower | packet99 DNR, packet52/53 | - |
| 11-bit enumerative decoder / Boolean-circuit decode | closed: 4.8x slower on device; 1,288-node circuit | packet162/162b DNR | - |
| (ii) subgroup-cooperative dequant with shuffles | closed in substance: "Divergent arbitrary-index lookup needs 64 32-bit shuffles per IQ2 octet"; R6 register-grid 1.45 ms vs 0.298 | p45 diagnosis note; packet25 DNR | - |
| (iii) one launch for the 10 routed experts | **already production** ("Batch all ten experts into one grid | Already production") | packet65 DNR | 0 |
| (iii') naive gate/up/down fusion | closed: "Down needs all rounded activated rows across workgroups. No legal grid barrier" | packet65 DNR | - |
| (iii'') routed activation as an epilogue of the split-stream gate/up (SLM exchange gate<->up inside the WG64, one barrier) | **open, unmeasured**: packet65 only *skipped* it ("About 4.7 us opportunity cannot reach broad-class 30% bar; skipped"); packet109 fused the *shared* activation/down/blend and proved exact SiLU epilogues are achievable here after four rejected NaN-payload forms | packet65, packet109 | 4-5 us/layer (+0.6%): above the 3.8 screen bar, below the 15.1 chain bar |
| (iv) software pipelining of scale/grid words into registers (prefetch64, E3, batch2/4) | closed: p65 prefetch64 larger code; p95 E3 -0.46%; p102 batch2 0.981, batch4 1.002; p115 under 256 GRF 1.175x | packet95/102/115 DNR | - |
| (iv') register-free LSC prefetch (`prefetch` to L1/L2, no destination register) of the next step's 64-B code line | **open, unmeasured**: every closed prefetch arm loaded into registers (p65/p95/p102: "extra registers/occupancy") or re-read bytes in a separate kernel (p119 warm loads 1.079x; p175 D2 warm-ahead 1.44x "reads the weights twice") | p95/p119/p175 rows close *those* mechanisms, not an instruction prefetch | <= engine - L2-warm = **<= 12 us** on gate/up; down unknown (no warm figure for tile16); p119 says extra requests compete |
| (v) Xe2 2D block loads | gate/up tile16 (the layout a 2D block load wants): micro 0.893/0.898, **engine 0 / -0.35%** ("no in-engine gain"); draft/shared/HC/router tile16 0.95-2.1x | packet104/104b DNR, packet142 | - |
| (vi) gate+up in one pass | **already production** (paired WG64); E5 shared activation loads 1.033x | packet102 DNR | - |
| (vii) other down distribution | tile16 in production (0.695); interleave 1.000; virtual2 persistent +26 us; large GRF 1.44x | packet100/53/115 | - |
| geometry sweeps (WG64/128, V4/V8/V16, SIMD16, persistent) | closed: V16 +52 us; persistent +138/+215/+218 us; "SIMD16 geometry-only sweep deferred: prior geometry losses" | packet53/53b/81 DNR | - |
| class layout / kernel-order weight placement | closed, null for attention/router/gdn.z; "Expert gate/up and HC were already ruled out by packet141 (1.22x cold/warm)" | packet142/145 | - |
| FP32 input copy | registered as `p27.fp32_input`, not selected by K2 | k2-class-registry | - |
| E2 full effective-scale cache in memory | closed: 9.44 GB does not fit | packet95 DNR | - |
| **(viii) instruction diet inside the exact identity** (never tried as such; every prior arm changed loads, tables, geometry or registers, and packet81's revisit condition is exactly "an ALU/latency analysis that predicts a gain"): (a) apply the sign to the product's sign bit after the multiply (`scale*float(-q) == -(scale*float(q))` bit-exactly under IEEE RN; the NaN/Inf scale path already branches separately) -> shl/and/xor (3) for shr/and/neg/sel (4); (b) byte-regioned extraction (`mov ... :ub` region) instead of shr+and; (c) hoist the IQ4 `d*float(level)` products: 16 products per 32-weight block then a 4-level select per weight (pure CSE: identical bits); (d) hoist the per-tile `exceptional` test to one uniform per-row pre-check so the hot loop has no goto/join | **open** | gate/up 16 -> ~12 instr/weight = **0-12 us**; down 15 -> ~11 = **0-7 us**; compiler may already emit (b); (c) adds 16 live floats per lane (packet53b spilled at 32 live sums) |

Memory notes that bind (found in the repo, quoted):

* notes/2026-10-11-first-exact-two-card-decode.md: "measured 3.4-5 us per launch on the card (9.5 us with a host wait after
  each)"; ". . . is bit-exact ... and 50-100 times slower per ..." (descriptor-interpreting fused kernels); packet46 note:
  "Descriptor-interpreting fused kernels remain closed."
* notes/2026-10-17-own-runtime-packet48.md: "compute/compute overlap: B70 has one CCS."; packet175: "the single CCS cannot
  overlap the warm kernel with other compute. Any variant that reads the weights twice is dead."
* notes/2026-10-18-own-runtime-packet90-result.md: "Packet 86 `exp-nodeq` bounds expert dequantization at about 1.14 ms per
  half" (= 0.68 gate + 0.43 down; 24 layers -> 28 + 18 us per call).
* INVENTORY.md (tuned-config lesson): "metadata is part of arithmetic identity ... Require explicit M=1 coverage: nearest-key
  dispatch can otherwise silently choose a larger tile."
* The Triton alignment-hint note does not apply (no Triton; SYCL `vec<...>::load` on 4-byte-aligned rows, packet65).

## C. Decision

**No credible path to >= 15.1 us/layer (two cards) with an exact expert kernel on the present evidence; a one-card
11.4 us is possible only in the optimistic case. NO-GO on a lever micro packet priced at +2%.** Reasons, with numbers:

1. The gate/up kernel is 48 us with its weights in L2 against a 20 us copy floor and a ~27 us exact-ALU floor; the
   remaining ~40 us/layer of gate/up excess is issue/dependency time of the exact 3-op identity plus decode, not bytes.
   No bytes-side mechanism can touch it, and the bytes-side mechanisms are closed (tables, prefetch into registers, tile16,
   layout, GRF, geometry) or memory-infeasible (expanded streams, +3.77 GB/rank).
2. The only open mechanisms are (iii'') the activation epilogue (4-5 us, exact-feasible), (iv') a register-free LSC
   prefetch (<= 12 us upper bound on gate/up, zero if the kernel is issue-bound, risk per packet119), and (viii) an
   instruction diet (0-19 us across both kernels, compiler-dependent). Sum of ceilings 4-36 us at 100% transfer; the
   class's transfer record is 0% (p104b, a 10% micro gain that vanished in the engine) to 47-100% (p100). The expected
   value is below 15 us; the one-card bar (11.4) needs >= 60% of the optimistic sum.
3. Fourteen expert arms since packet48 produced one in-engine win (tile16, a memory-pattern change); the kernel's binding
   term is now the one tile16 did not touch.

**The single most informative measurement (one lane-B window, ~5 min, before any candidate work): an issue-floor
decomposition of the two record kernels** -- production `p90exp::Kernel<IQ2_S,2560,64,false,true>` and `p100::Kernel<2>`,
real bytes, three conditions each: (1) DRAM-cold on packet100b's 384 real routes with the 512 MiB device scrub
(packet100 harness, `micro_gate.py` geometry checks `scrub_bytes 536870912`); (2) L2-warm (packet162b harness: compact
10-expert bank, 200 A/B pairs); (3) **no-load**: the identical kernel with the expert-row base pointer aliased to one
L1-resident 16-row slab (same instruction stream, every weight load an L1 hit; non-exact diagnostic, outputs discarded).
Decision rule: if warm (2) and no-load (3) agree within 10% for gate/up (expected: 48 +- 5 us), the class is issue-bound
and only (viii) can move it -> brief the diet as an exact candidate with a <= 0.85x micro gate; if (3) is <= 0.75 x (2), the
dependent-load latency is real and (iv') LSC prefetch is the candidate; down's split decides whether (viii-c) is worth
its register cost. Without this split, both candidates are coin flips below the bar.

### If the measurement reopens the class: the candidate micro packet (pre-specified so no second study is needed)

* **Harness:** packet100b's real-route micro (`packet100b-route-capture/run_micro.py` + `packet100-down-locality/micro_gate.py`:
  384 captured target routes, 40 alternating pairs per route, both orders, 512 MiB scrub, FP32/BF16/status byte equality
  per route before timing, qualification <= 0.85 in both orders and every stratum) for the engine-equivalent cold
  numbers, with packet162b's `micro.cpp` (200 A/B pairs on a compact bank, 25,684 output/status/error bytes incl. invalid
  expert 512 and a partial-row route, NaN fixture) as the warm/exactness leg. Both already run under the shared v4 lane
  wrapper on physical card 2 (`0000:43:00.0`), no model load.
* **Candidates (named shapes, not ranges):** C1 `exp-diet` gate/up: p90 E1 WG64/V8 geometry unchanged, decode rewritten per
  (viii a, b, d). C2 `down-diet` tile16: (viii c, d). C3 `exp-act-epilogue`: C1's kernel + SLM gate<->up exchange and the
  `p39::activation` epilogue (removes the expsact launch); counted against gate/up + act time. Shapes: the record's
  (gate/up 640 x 2560 x 10 experts IQ2_S E1 rows; down 2560 x 640 x 10 IQ4_NL tile16), layer-0 and layer-24 expert sets
  for the warm leg as packet162b did. No geometry, table or prefetch arms.
* **Duration:** packet100/100b measured "six minutes each" for 384 routes x 80 samples x 2 candidates; three candidates
  ~9 min; the warm leg 1,600 events ~5 min; watchdog 1,800 s (>= 4x). Two fresh processes only if a candidate qualifies.
* **Lane / memory:** lane B, card 2 (or 3), endpoints stopped, PAUSE-A held as for packet162b/100b. Device: full banks
  550 MB (gate/up) + 471 MB (down) + outputs < 1.2 GB; host: route file 46 KB + pinned fixture rows < 100 MB; root >= 25 GB
  free; build < 300 MB; nice 19, cores 8-15,24-31, one compile at a time (packet162b/100b rules).
* **Exactness gate:** bit-identical BF16 outputs, status, peer_status and error words on all 384 real routes and on the
  packet162b fixtures (finite seeds 0/1, NaN/Inf/subnormal/signed-zero fixture 2, invalid expert 512, partial row range),
  GNU and Intel host twins, two fresh processes each, before any timing is read; no payload canonicalization (packet54/109
  rows: a `0x7fc0` vs `0x7fc1` NaN is a failure). C3 additionally against the production `expsact` bytes.
* **Kill rules:** any byte difference -> candidate closed, no timing reported; ratio > 0.85 in either order or any route
  stratum -> closed with its DNR row; warm/cold disagreement > 10% on the control -> withhold (packet141 rule); micro gain
  < 15% of gate/up+down+act (= ~15 us) -> no engine screen; a second process only for a qualifying candidate; no retry, no
  reseal after a result exists (packet125 rule).
* **Chain of evidence before integration:** (1) CPU byte identity GNU+Intel x2; (2) device micro qualification JSON
  (both orders, all strata); (3) exact one-load v5 bracket control/candidate/control/candidate/control on lane B at the
  record selection (drift <= 0.5%, 12/12 exact, acceptance unchanged); (4) lane-A confirmation beating both fresh
  controls by >= +0.5% (review 13 rule), chain only at >= +2% (chain-waiter rule); (5) packet DNR rows written either way.

One-card note: the same kernels serve the one-card line (synthesis 1: 0.479 vs 0.486-0.495 ms/layer); its expert class
also carries 1.0-1.5 ms/token of host miss reads that no kernel change touches, so a kernel saving transfers at the same
per-layer rate there (11.4 us = +2%), and the optimistic diet+epilogue sum (~15-20 us) would clear it; the measurement
above is the gate for both lines.

## Sources read (absolute paths)

* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/{p49b_gemv.hpp,p49b_expert_kernel.hpp,p49d_expert.hpp,p49d_expert_submit.cpp,p65_expert.hpp,p90_expert.hpp,p90_layout.hpp,p95_expert.hpp,p100_down.hpp,expert_down.cpp,p42_expert.hpp,p33_candidates.hpp,dispatch_registry.hpp,k2-class-registry.json,dispatch-speed6.json,p39_fused.hpp}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/v5/{evidence/build.json,lineage/k3x/selection.json}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/{build/device-cards01-p190-a/K2/run0/summary-k2-measured.json,analysis/lever-synthesis-4-20261022.md}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/{README.md,v5/evidence/analysis.json}; notes/2026-10-22-packet191-k3x-class-attribution.md
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet110-class-roofline/{ROOFLINE.md,roofline.json,run_micro.py,microbench.cpp}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/README.md; notes/2026-10-18-own-runtime-packet86-verdict.md
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet81-experts3/{ANALYSIS.md,evidence/instruction-mix.json,evidence/registers-production/kernel-1.asm.gz,kernel-3.asm.gz}; packet65-expert-occupancy/OCCUPANCY.md
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/{README.md,MICRO162B.md,micro.cpp,evidence/enum11-diagnostic-B1/analysis.json}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet99-iq2-grid/{DIAGNOSIS.md,WINDOW.md,microbench.cpp}; packet100-down-locality/micro_gate.py; packet100b-route-capture/{run_micro.py,qualification.py,capture_inputs.py}
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet182c-chain/analysis/onecard-synthesis-1-20261022.md
* /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet{20-launch,25-gemv,48b-production,125-miss-transfer,141-transfer-gap}/README.md
* DO-NOT-REPEAT.md of packets 65, 73, 81, 95, 99, 102, 104, 100, 119, 162, 49b, 49d, 53b, 53, 54, 25, 125, 141, 142, 145 (collected in dnr-packets.txt / dnr-expert-raw.txt beside this file); packet173 LEVER-TABLE.md row 6 (E1n2 +0.22%)
* notes: 2026-10-17 packets 65/73/81/53b/54/48-device/49d; 2026-10-18 packets 90/95/99/100-micro/102/104-micro/115-micro/119-micro/125-micro/141/142/145/109; 2026-10-19 packets 162/175; 2026-10-11 first-exact-two-card-decode; 2026-10-17 packet48 (one CCS); packet7-kopt2/analysis.json (device properties)
