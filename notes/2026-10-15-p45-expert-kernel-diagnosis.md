# Packet45 expert-kernel diagnosis — 2026-10-15

**The expert kernels do much more work per fetched weight byte than the streaming test.** IQ2/IQ3 pay for dependent codebook gathers, integer extraction, exact scale handling and separately rounded products/additions. IQ4 pays for a branch-heavy integer lookup, many small loads and four times as many short row groups. There is ample grid parallelism; a small token batch does not mean only ten work-groups. Current evidence does **not** identify a measured cache-miss rate, occupancy percentage or single dominant stall. It supports these mechanisms and bounded experiments, not a promise of 600 GB/s.

**First experiment: current fused IQ4 down/status versus bank/vector down with the identical status tail.** It changes one body, keeps one launch and the same storage, and targets all 48 layers. The working estimate is only **0.093/0.101 ms saved per rank-0/rank-1 target half**, with zero or a regression possible. The existing IQ2 packed body composed with its checks is next, about **0.063/0.072 ms**. Larger exact rewrites below remain research candidates with a no-effect planning prior.

This is a CPU-only, read-only diagnosis of the packet trees, starting at main `593922498`. Only this note and [its evidence helper](p45_expert_kernel_diagnosis.py) were written. Shell/Python work ran at nice 19 on cores 4–15,20–31 with `python3 -B`. No compiler, device binary, device access, sudo, model load or server was used. No kernel was implemented or qualified here. The 90-minute time box is an upper bound, not a requested benchmark duration. CURRENT.md and existing negative-result indexes stay untouched under the requested write scope.

## Evidence and the actual baseline

`P45` means [packet45-merged3](../experiments/own-xpu-runtime/stage2/packet45-merged3/), `P42` means [packet42-codegen2](../experiments/own-xpu-runtime/stage2/packet42-codegen2/), and `P11` means [packet11-kopt6](../experiments/own-xpu-runtime/stage2/packet11-kopt6/).

Primary timings are `P45/build/speed7-c4096-dr1-s23-cards01-gpu/K2/run0/{summary.json,events.jsonl.gz}`. The helper verifies the decompressed event hash, all 200 repetitions per arm, exact flags, stage counts, eight-buffer rotation and medians for the three fusion comparisons. These are retained measurements, not new measurements. The [roofline study](2026-10-15-p45-roofline-and-structural-levers.md) and [lever-2 design](2026-10-15-p45-lever2-design.md) supply the 23/25 layer placement and prior composition proposal. The helper independently recomputes the byte arithmetic and four-run timing totals.

| Current executed class | Selected implementation | Useful weight bytes/site | K2 event-sum µs | Effective GB/s | 600 GB/s floor µs |
|---|---|---:|---:|---:|---:|
| IQ2_S gate/up + checks | P39 `expert_checks`, P28 paired body | 10,496,000 | 80.416 | 130.52 | 17.493 |
| IQ3_S gate/up + two checks | P28 paired WG32, two separate check kernels | 14,080,000 | 90.9375 | 154.83 | 23.467 |
| IQ4_NL down + status | P39 `down_status`, **P33 select/scalar** body | 9,216,000 | 93.437 | 98.63 | 15.360 |

Numerators are selected payload, not the 512-expert resident bank: gate/up is `10*640*2*(2560/256)*(82 or 110)` bytes; down is `10*2560*(640/32)*18`. P39 fixture `payload_bytes` reports the full bank, so dividing that field by event time would overstate useful bandwidth by **51.2×**. All GB/s here are decimal useful-weight rates, not memory-controller counters. Activation/codebook reads, cache-line overfetch, output/status writes and repeated cache-level traffic are outside that numerator.

Rank 0 has 22 IQ2 sites, one IQ3 site and 23 down sites; rank 1 has 25 IQ2 and 25 down. Hence `22*g2+g3+23*d` / `25*(g2+d)` = **4.009141/4.346325 ms** per target half, and useful-byte memory floors **0.7616/0.821333 ms**. Across SPEED6/7 and both pairs these proxies span **4.009–4.043 / 4.346–4.383 ms**. They are K2 isolation costs multiplied by plan counts, not a captured pipeline profile. Savings on the two parallel halves cannot be added into a token-latency claim. The INT8 draft expert kernel is different and receives no credit here.

The generic dispatch says `expsdown=p33.down.bank`, but [main.cpp](../experiments/own-xpu-runtime/stage2/packet45-merged3/main.cpp) intercepts P39-tagged sites before generic GEMV dispatch. [p39_fused.hpp](../experiments/own-xpu-runtime/stage2/packet45-merged3/p39_fused.hpp), `lanes`, explicitly calls `p33::down_lane<1,K>`: select/scalar. Gate/up similarly calls `p28::expert_lane<T,K,false,true>`. Diagnose those bodies, not the generic winning names.

## Geometry, reductions and launch overhead

The production case is **M=1 token**. “Paired” means gate and up projections on the same input, not M=2 tokens. There are ten distinct routed experts from 512, each with 640 gate/up rows at K2560 and 2,560 down rows at K640. These quantization labels are tensor formats within the quantized compressed model, not a change of model precision.

[p39_sycl.hpp](../experiments/own-xpu-runtime/stage2/packet45-merged3/p39_sycl.hpp), `gemv`, issues one SG32/WG32 per output row and expert slot: **6,400 groups** for paired gate/up, **25,600 groups** for down. Every lane owns eight consecutive coefficients, then advances by 256. Gate/up has ten full tiles; down has two full tiles plus a 128-weight tail. Its useful lane-tile fraction is `640/(3*256)=83.3%`. That tail alone cannot explain 16.4% of streaming bandwidth. Whole-grid work is plentiful; register/dispatch resource occupancy and dependency hiding within an engine are the unresolved questions.

Down has four times the group count, half the total scalar weight count and only 16 or 24 terms per lane, versus 80 terms per projection for gate/up. Address/route setup, final reduction and stores are therefore much less amortized. Gate/up computes two dot streams while reusing the input load; down has one stream and a slot-specific input. This is a credible reason the smaller down payload takes longer, without claiming measured work-group scheduling cycles.

Each stream preserves the adjacent SG32 tree at widths **1,2,4,8,16**, with separately rounded additions; only lane 0 stores BF16. Gate/up does ten shuffle/add stages per row pair, down five per row. There is no cross-work-group sum or atomics in the dot reduction and no SLM/barrier in the selected P39 expert paths. The P28 IQ3 WG32 path also has no executed row-group barrier; its generic source declares a local accessor, but the retained matching GEN has no SLM messages. Removing that source declaration alone is not a performance mechanism.

There is **no host launch per selected expert**: slot is part of the grid. One route descriptor is reused logically across rows, but each row group loads/validates it and computes an expert-row address. The ten descriptors are tiny; their dependent address calculations and repeated instructions can matter, but their DRAM bytes do not explain milliseconds. Random expert IDs spread reads across the bank; within each selected expert, row bytes remain contiguous. Row strides are 820/1,100/360 bytes for IQ2/IQ3/IQ4, and packed blocks are 82/110/18 bytes, so arbitrary wide aligned loads or padded-row assumptions are unsafe.

For **M=2**, preserve two independent input/accumulator/reduction streams and route lists. Two tokens need not select the same experts; only their actual intersection permits expert-weight reuse. Doubling private decoded arrays or accumulators can reduce occupancy, as the old paired-input failures demonstrate. The current paired path already shares one token's input between gate/up. A two-token verifier also has ordered recurrent-state/attention dependencies outside these kernels. No M=2 speedup, common-route rate or per-half saving is assumed here.

## Decode work and lookup behavior

The source chain is [P28 expert decode](../experiments/own-xpu-runtime/stage2/packet45-merged3/p28/expert.hpp), [P33 down](../experiments/own-xpu-runtime/stage2/packet45-merged3/p33_candidates.hpp), and [P42 packed candidates](../experiments/own-xpu-runtime/stage2/packet45-merged3/p42_expert.hpp). The more relevant native evidence than packet11 is P42's [expert report](../experiments/own-xpu-runtime/stage2/packet42-codegen2/expert-report.md), [blind assembly review](../experiments/own-xpu-runtime/stage2/packet42-codegen2/launch-expert-blind-review.md), [codegen receipt](../experiments/own-xpu-runtime/stage2/packet42-codegen2/expert-codegen.json) and retained `expert-assembly/*.asm.gz` / `*.zeinfo.gz`.

Those are hash-bound **historical offline bodies**, not the final P45 fused binary's JIT assembly. No matching P45/P44 assembly or spill report was found in their build trees by filename search. The helper checks all eight P42 uncompressed assembly hashes and selects the matching kernel's execution metadata; a `.zeinfo` file contains other kernels too. Whole-module barrier/SLM counts would be wrong for the selected WG32 entry.

The following conditional GEN paths assume valid routes, normal finite scales and full tiles. They include gate-loop bookkeeping but exclude prologue/reduction. A “message” is a SIMD load instruction, not a cache miss, cache line or DRAM transaction.

| Body | Compared weights across SG32 | Unique packed weight bytes | GEN instructions | Data messages | GEN instructions / unique byte |
|---|---:|---:|---:|---:|---:|
| P28 paired IQ2 | 512 (8 per lane per projection) | 164 | 392 | 22 | 2.39 |
| P28 paired IQ3 | 512 | 220 | 418 | 22 | 1.90 |
| P42 packed IQ2 | 1,024 (two loop tiles) | 328 | 859 | 32 | 2.62 |
| P42 packed IQ3 | 512 | 220 | 459 | 18 | 2.09 |
| P33 down select/scalar | 256 | 144 | 290–306 homogeneous; 482 mixed-arm union | 17 | 2.01–3.35 |
| P33 down bank/vector | 256 | 144 | 188 | 7 | 1.31 |

The last column normalizes **SIMD instruction entries across a subgroup**, not per-lane scalar instructions or cycles. Mixed SIMD16/32 execution widths, masks and dependencies prevent converting it into an instruction roofline. It demonstrates that a packed byte is not a streaming byte of work. It does not prove down bank must beat select.

**IQ2:** each projection decodes a 10-bit grid index, sign bits, a half block scale and a nibble subscale. Eight integer magnitudes must be converted, signed and scaled, then multiplied by BF16-widened inputs and accumulated with separate rounding. The finite source folds sign into the integer; exceptional scales retain magnitude-then-sign arithmetic. Gate and up have different weights/codebook indices; only activation data and some addressing can be shared. Ten tiles retain two accumulation chains plus scale/index/decoded-value live state.

The IQ2 codebook is **8 KiB** (1,024 octets); IQ3_S is **2 KiB** (512 four-byte entries). For one SG32 paired tile both logically request 512 bytes of magnitudes, in addition to 512 bytes of BF16 input, against just 164/220 unique packed weight bytes. Those logical requests can hit cache or coalesce; they are not 1,024 extra bytes of DRAM per tile. These small shared grids are plausible cache residents. Packed weights → index/high-bit → codebook address → gather → extract/convert → multiply is nevertheless a serial dependency chain even on a hit. The receipts have no cache counters to establish hit rate, conflict rate or gather latency. Eight-bank weight rotation does not make the small common codebook cold.

P28's byte-table **source** does not imply eight byte loads from each grid in GEN. The reviewed paired paths use four d32 table messages in total. P42 IQ2 combines each projection's pair into a d32x2 gather and explicitly packs the input loads: 22→16 messages per paired tile, while instructions rise 392→429.5. P42 IQ3 retains two independent grid indices per projection; packing inputs yields 22→18 messages, while instructions rise 418→459. The codebook footprint and encoded byte numerator also differ: IQ3's higher effective GB/s is partly its 34% larger payload for nearly the same scalar work, not evidence of a faster memory subsystem.

Matched SPEED7 bare-body timings support a modest message/dependency improvement for IQ2: **82.396→76.667 µs**, versus only **83.750→82.813 µs** for IQ3. They do not support a many-fold expert speedup. Reread aggregate gate controls are about 160 µs against about 166 µs rotated; down bank is 98.229 reread versus 101.4065 rotated. This small cache-mode response is consistent with substantial non-DRAM cost, but both workloads may exceed a relevant cache and table/input caches are shared, so it is not a DRAM-stall fraction measurement. P39's current comparisons contain **rotated only**, not a measured fused reread A/B.

**IQ4:** no IQ2/IQ3 grid exists here. The 16 signed nonlinear levels are implemented by nested selects in the current fused body, not a global table. Retained select GEN has divergent branches; if lanes choose multiple arms, more paths issue. Each full tile's scale conversion, eight scalar code and eight input messages, nibble selection, integer-to-float conversion, scale multiplication and product/add chain are expensive relative to 144 bytes of unique packed weight. Four lanes logically read the same half scale; pairs consume low/high nibbles of the same code bytes. Cache reuse does not remove message issue or address/lookup dependence.

Bank/vector uses four packed immediate banks and a variable shift/sign extension, plus explicit complete eight-value loads. It removes table access/branch structure without altering levels. But the historical packet33 select winner was faster than bank despite more counted instructions/messages. More decisively, [packet42 card-2 timing](../experiments/own-xpu-runtime/stage2/packet42-codegen2/receipts-card2-20261012/summary.json) found select/vector **106.042 µs versus 89.791** select/scalar, and bank/scalar **110.625 versus 89.792**, all byte checks passing. “17→7 sends” is therefore not a sufficient diagnosis or forecast. P45's present bare bank/select ordering differs (101.4065/109.479); changed wrapper/codegen identity matters. Only a matched **fused** A/B settles D1.

## Register pressure, checks, and what packet11 actually proved

The matching P42 metadata says **128 GRFs, SIMD32** for all eight inspected entries. That is allocation mode, not live-register count or achieved occupancy. P28 paired IQ2/IQ3 report predicate flag stores/loads **24/28**; packed candidates **5/8**; down select **2/2**, bank none. No GRF scratch-spill size is reported for these entries. Predicate spills are not automatically off-chip GRF spills. The final fused P45 register assignment remains unknown. Two decoded float8 arrays plus two accumulation streams make live-range growth a credible risk, but it is not evidence that current P45 spills.

The valid-path P39 check/status tail is small. Lane 0 writes results; row-zero groups write 10 down statuses or two sets of 10 gate/up statuses. `sticky_fail` performs a compare/exchange only for an invalid route when active; there is no contended valid-path atomic per output. In particular `expert_checks` is not `expert_act`: it does not run the SiLU tail or all-route validity reduction on every row. The selected IQ2 and down kernels already removed the separate check launches. Disabling checks would violate exact behavior and would not explain their remaining cost.

The measured complete comparisons are IQ2 **88.7505→80.416 µs** (three events→one), IQ3 **90.9375→83.542** (three→one), down **115.104→93.437** (two→one). About 3.44 µs per separate check appears in the IQ3 event distribution. Those are device events, not host launch latency. Fusion savings include changed kernel compilation as well as removed events: down's 21.667 µs gap is far larger than a single tiny check. K2 sums event durations and omits inter-event/host gaps; record both full span and host time in future tests.

[P11 timing](../experiments/own-xpu-runtime/stage2/packet11-kopt6/receipts-card3-20261011/timing.json) localizes its regression to **gate/up**, not unchanged down or the weighted epilogue. Layer0, first owner:

| P11 variant | Complete three-stage span ms | Gate/up ms | Down ms |
|---|---:|---:|---:|
| experts_sg32 | .298906 | .172032 | .125104 |
| register_grid | 1.453541 | 1.324480 | .126719 |
| slm_pair | 2.336875 | 2.209948 | .125417 |
| packed_pipeline | 2.600000 | 2.472865 | .125417 |

Second fresh owner agrees: .298802 / 1.452448 / 2.349271 / 2.623750 ms. Packet11 uses WG128, four row subgroups, and a separate grid dimension for gate/up matrices; today's paired WG32 body is a different baseline. Its old 66 GB/s complete-block rate cannot replace today's class rates.

The [retained P11 assembly receipt](../experiments/own-xpu-runtime/stage2/packet11-kopt6/assembly-receipt.json) and local `build/isa-evidence/*.asm.gz` verify the **6,016-byte IQ2 register-grid spill** and 2,167 estimated GRF references. Divergent arbitrary-index lookup needs 64 32-bit shuffles per IQ2 octet (32 for IQ3), not one shuffle. The SLM candidate copies 8 KiB/2 KiB **per work-group**, barriers, and holds two activation octets; with 3,200 gate/up groups, IQ2 alone stages about 26.2 MB of grid data before reuse. Pipelining keeps current/next octets and subgroup scale broadcasts alive. Those additions plausibly increase dependency and scheduling costs.

Crucially, the SLM and pipeline dumps report **no GRF scratch spill**, yet regress the most. No-spill is necessary protection, not proof of good occupancy or good scheduling. P11's smaller counted consume regions excluded fetch/broadcast/setup and could not price their dependencies. The report's claim that broadcast/SLM caused the slowdown is a mechanism hypothesis; counters did not isolate them. The older decode region's 145/138 instructions and 225/237 SIMD16 issue equivalents per octet are historical, not counts for current P28/P39. Packet33's [cost-model review](../experiments/own-xpu-runtime/stage2/packet33-codegen/model-notes.md) likewise found that adding spills improved training fit but **held-out R² became −0.246**. Do not resurrect its predictions.

Current K2 also already rejects P28 paired rows4 (IQ2 **85.417 vs 81.979**, IQ3 **88.646 vs 83.698**) and shared-scale WG32 (**88.021 vs 81.979**, **91.198 vs 83.854**). P33 restrict-only gate regresses to **100.520/103.541 µs**. P25 paired-input had retained **2,560/7,808-byte IQ2/IQ3 spills** and poor timings. These rule out blind group-size, broadcast, restrict, full-grid-register, SLM and multi-tile-pipeline sweeps. They do not rule out a new bounded-live body with verified different generated code.

## Exact candidate definitions — two per class

Every candidate preserves weights, layout, scale equations, separate product/add rounding, lane-term order, adjacent reduction tree, BF16 stores, all status/error outputs, invalid-route NaN bytes, and active/sticky behavior. No FMA, reassociation, split-K, new precision, padding assumption or removed validation is allowed. These are **intended bytes_equal designs**, not claims that new device binaries already pass. Do not canonicalize NaNs to make a check pass.

**IQ2 G1 — packed body inside the existing fused checks.** Substitute `p42expert::gate_lane<IQ2_S,2560>` for the P28 lane body inside P39 `expert_checks`, retaining SG32/WG32 and the tail verbatim. Two packed uint32 grid words per projection and packed BF16 input requests reduce dependent messages without a resident expanded weight table. This is the already-unapplied [lever-2 design](2026-10-15-p45-lever2-design.md), not a second claim of invention. Existing bare measurements justify testing composition; they do not qualify it. K2 compares fused old/new directly, per IQ2 format, with the original parent-fusion gate intact.

**IQ2 G2 — single-tile packed decode consumed immediately.** New alternative to G1, not a copy of P11 pipelining: keep only the current tile's packed integer words/signs/scales, then for `j=0..7` decode one gate/up pair and immediately update its two original accumulators. Retain the packed BF16 input tile; eliminate simultaneously materialized `float a[8], b[8]`. Keep the column loop rolled (unroll factor one); allow only the eight-element inner spelling to unroll. Preserve exceptional-scale spelling using a separate unchanged fallback. Require GEN to show no next-tile fetch/live decoded arrays, no new broadcast/SLM and no scratch spill. The desired mechanism is shorter live ranges and fewer predicate/register moves while preserving paired input reuse. Compiler scheduling could instead worsen; use a no-effect central forecast. Compare against current fused P39, and against G1 if G1 qualifies; never add their savings.

**IQ3 Q1 — packed body and the two checks in one fused kernel.** Use `p42expert::gate_lane<IQ3_S,2560>` with P39's existing IQ3 check tail, measuring against the **actually selected P28 + two checks** and retaining a current-body fused control. The small packed-body gain alone cannot qualify global `expsgate`, and P39's current 8.13% IQ3 fusion gain falls short of its **10%** light-class threshold. A new combined comparison must clear that unchanged bar; it may not activate a parent previously declined on the strength of a body-only comparison. Central forecast is still below the required gain, so expected dispatched saving is zero. Do not lower the threshold for one exceptional layer.

**IQ3 Q2 — bounded-live version of Q1.** Apply G2's immediate consumption and one-tile live-state bound to the two IQ3 four-byte grid indices per projection. No large LUT staging, sharing broadcasts or paired future blocks. The mechanism targets the current paired body's predicate/register pressure while preserving its two independent grid addresses. Keep current P28+checks as the baseline and Q1 as a secondary same-owner control. This is only one layer on rank0: do it when the common G2 machinery supplies it cheaply, not as its own tuning campaign. No-effect prior; target/range below is explicitly unmeasured.

**IQ4 D1 — bank/vector body inside the current fused status kernel.** Use `p33::down_lane<0,640>` instead of `<1,640>`, preserving P39 geometry, route checks, exact tree, BF16 conversion and status/error writes. This composes the current bare bank winner with the existing fusion; it does not disable P39. First target is fewer dependent lookup branches/small input/code messages without added live tiles. It is the smallest implementation change and already has the lever-2 patch design. Historical bank/select reversals make the estimate uncertain.

**IQ4 D2 — SG16 implementing the original 32 virtual lanes.** A new bounded geometry experiment, **not** setting `reqd_sub_group_size(16)` on the old kernel. Physical lane `l` owns original virtual lanes `2*l` and `2*l+1`, each with its own accumulator visiting `k=8*v+256*n`, increasing `j=0..7`. Their 16 adjacent weights share one IQ4 block scale without a shuffle; consume them without retaining two decoded float arrays. After both streams finish, compute `a[2*l]+a[2*l+1]` locally. Then SG16 adjacent additions at widths 1,2,4,8 exactly reproduce original SG32 widths 2,4,8,16. Do not interleave terms into one accumulator. Keep the 128-weight tail and invalid-row values exact. One row per WG16, all ten experts in one grid, same status tail, no local accessor/barrier/new buffer. Potential gains are fewer repeated scale/address calculations and narrower SIMD register/control handling; risks are more per-lane live state, less latency hiding and altered compiler scheduling. The reduction proof makes it eligible for byte tests, not inherently faster. Compare first with the current fused kernel; compare with D1 if that wins. Keep a no-effect central estimate and a bounded 75–115 µs sensitivity range. No wider geometry sweep follows a loss without new evidence.

## Ranked planning estimates and uncertainty

These are **planning scenarios, not measurements, confidence intervals or hardware bounds**. Rank is by central raw K2 saving; zero-prior research candidates are tied, with implementation cost breaking the tie. Ranges deliberately include regressions and are not guarantees against a worse compiler failure. All rates use the same useful-byte numerator and complete class event sum as the baseline.

G1/D1 central times subtract **half** the observed bare-body delta from the current fused time. The favorable endpoints subtract all of it; the unfavorable endpoints allow a fusion regression. Q1 starts with measured current-body fused IQ3 and subtracts half its small bare packed delta. This is the previous design's conservative transfer assumption, not a fitted model. G2/D2/Q2 have no matched new-code measurement, hence zero-effect central priors; their ranges are explicit experimental sensitivity targets. CPU source reasoning cannot supply a defensible positive expected gain for them.

| Rank | Candidate | Expected effective GB/s (sensitivity range) | Central µs/site | Rank0 ms saved (range) | Rank1 ms saved (range) | Evidence / admission outlook |
|---|---|---:|---:|---:|---:|---|
| 1 | D1 IQ4 fused bank/vector | **103.1** (90.4–108.0) | 89.401 | **.093** (−.197 to .186) | **.101** (−.214 to .202) | Small composition; >3% possible, uncertain |
| 2 | G1 IQ2 fused packed | **135.3** (122.0–140.5) | 77.552 | **.063** (−.123 to .126) | **.072** (−.140 to .143) | Repeated bare-body improvement; >3% possible |
| 3 | Q1 IQ3 fused packed | **169.5** (149.8–178.2) | 83.074 | **.0079** (−.0031 to .0119) | 0 | Central case fails 10%; **zero adopted saving** |
| 4= | G2 IQ2 bounded-live packed | **130.5** (110.5–149.9) | 80.416 | **0** (−.321 to .229) | **0** (−.365 to .260) | New code; no-effect prior |
| 4= | D2 IQ4 virtual32/SG16 | **98.6** (80.1–122.9) | 93.437 | **0** (−.496 to .424) | **0** (−.539 to .461) | New geometry; greatest unverified upside/risk |
| 4= | Q2 IQ3 bounded-live fused | **154.8** (134.1–185.3) | 90.938 | **0** (−.0141 to .0149) | 0 | Common-code follow-up only |

`delta_ms = occurrences*(old_us-new_us)/1000`; `GB/s = useful_bytes/(1000*new_us)`. D1+G1 would save **.156/.173 ms per half** in the central composition scenario, before pipeline overlap and dispatch gates. They do not close the 3.25/3.53 ms memory-only gap. Alternatives within a class are mutually exclusive, and no draft saving or model tok/s forecast is added. IQ3's absolute elimination ceiling is only .091 ms on rank0; its realistic few-microsecond opportunity belongs last in engineering priority despite a positive conditional row.

## Single cheapest decisive microbenchmark and selection

**Name: `D1: fused IQ4 bank-versus-select, K640/R2560/top10`.** One independently admitted B70, one focused K2-style fixture, current P39 down/status versus D1, **bytes_equal against the current kernel**. No need to run the whole model, all K2 classes, another geometry or a profiler. This note does not authorize device work; the present task ends at this design.

Use the full 512-expert resident bank and eight weight-bank rotations from `P39Fixture`, not ten-expert-only allocations or repeated easy indices. IQ4 weights alone occupy `8*512*2560*360 = 3,774,873,600` bytes. Keep the existing bounded staging slab and host-memory admission; there is no reason to allocate two copies of every arm's weights. Same weights/activations/routes serve both arms. Preserve the baseline seeded workload for timing and include additional deterministic varied code/scale/route cases in equality gates; no hand-picked codebook branch distribution.

Run complete snapshots of BF16 outputs, statuses, sticky error and untouched output/sentinel buffers before/after timing. Required cases include ordinary routes, changed input, all 16 levels, zero/subnormal/extreme/exceptional scales and inputs, invalid/duplicate/empty/partial routes, row tails, inactive and pre-seeded error. Retain exact NaN-byte mismatches as failures in the declared scope; a category-only comparison is insufficient. K640 production timing is distinct from any odd-K arithmetic diagnostic. G1/G2/Q1/Q2 additionally compare both projection outputs and statuses; D2 checks lane accumulators/tree boundaries in the CPU proof before device equality. A deliberately corrupted output must fail the comparator.

Use eight untimed preflight repetitions, **200 alternating paired repetitions per mode**, and eight postflight repetitions. Primary is eight-bank rotation with incumbent `i%8`, candidate `(i+4)%8`; also collect an explicitly labeled reread mode. Neither is a model-performance headline. Record source/build/options/fixture identities, per-event start/end, stage count, buffer index, full-bank allocation **and selected useful bytes**, full execution span, host enqueue/drain time, median/p90 and hashes. Use separate fresh owners twice, reversing arm order in the second; this is one focused benchmark definition, not a server or restart loop. A first run can decisively reject a loss; a speed verdict needs both fresh owners.

For D1, the unchanged strict >3% K2 rule requires **<90.634 µs**, equivalently **>101.684 GB/s**, against this retained baseline; actual selection uses the fresh matched incumbent, not that fixed historical number. G1 similarly needs **<78.004 µs**, about **>134.56 GB/s**. IQ3 Q1/Q2 need **<81.844 µs**, **>172.03 GB/s**, under the current >10% light-class guard. Every registered workload and all bytes must pass, with all repetitions/stages/cache modes and no same-kernel identity masquerading as a win. No guard is relaxed to admit a forecast.

D1/D2 and G1/G2 require a closed **fused-body** comparison/dispatch modifier against current `p39.epilogue`, with parent enabled, type checked and fallback to the untouched parent's body. The existing [lever-2 design](2026-10-15-p45-lever2-design.md) already specifies this for D1/G1. Q1/Q2 instead need a complete combined IQ3 fusion entry versus the selected unfused three-event chain, so an unselected parent is not silently enabled. A generic `expsgate` class still must pass both formats; splitting an explicitly registered fused IQ2 comparison is transparent specialization, not hiding an IQ3 loss. Runtime adoption and source-bound fixtures must prove the selected body is the one executed.

Before an eventual device run, inspect the **actual new fused** generated kernel, including runtime-equivalent compile/link options: final text identity, SIMD width, GRF mode, scratch size, predicate spills, data messages, barriers and the finite/exceptional CFG. Do not rebuild anything during this diagnosis. Reject full-grid register staging, extra SLM/barriers, speculative double-tile live state or new GRF scratch spills. G2/Q2 must show a real live-range/code change; if the compiler emits the old body, close the candidate without timing a fake variant. D2 must show the virtual-lane tree unchanged. Zero spill is only a filter: a byte-exact but slower native candidate is rejected promptly, as packet11 requires. No massive instruction sweep or repeated retries.

A successful microbenchmark selects an operator candidate only. Subsequent admitted exact model-state/token gates and fresh-process pipeline comparisons are still required. On any device fault the coordinator follows existing evidence-first host recovery rules; this read-only task performs none of those operations.

## Reproduction and retained identities

Run only the read-only helper, from the repository root:

```bash
taskset -c 4-15,20-31 nice -n 19 python3 -B notes/p45_expert_kernel_diagnosis.py
```

It uses the standard library, imports no packet modules, refuses filesystem writes/child processes/network through an audit hook, checks affinity/nice, streams compressed K2 events, verifies retained assembly hashes, prints exact timings/spill metadata and recomputes every forecast. It does not regenerate timings or inspect hardware. Local K2/old assembly artifacts remain in their original storage; nothing was copied or deleted. If those ignored artifacts are later archived, restore them through their owning packet's retention instructions rather than fabricating inputs. The tracked P42 assembly and P11 JSON evidence remain directly reviewable.

| Input | SHA256 |
|---|---|
| SPEED7 cards01 K2 summary | `550f2b0a4f3a7d64c87ca1d7616833e028ec2e63f04bca8fc8a44e90df9f0da8` |
| Same decompressed events | `c11033b451b74c133bef5c3c116cc5de30499d82cae5e1a5792e150cd8ea0faf` |
| P42 expert-codegen.json | `a78612bf8b15b4333db7739155c355dd62dce068d67d09157d7934aa58f86ebd` |
| P42 card2 timing summary | `b4b041ef9cd9d3c9350e530c6b6f6aac3902c0d7a7d0a0a0d77d09356d62649e` |
| P11 assembly-receipt.json | `c71b19d8975822d49528324ad6202376f631b5f35bc06275cd6da3658e67cf9d` |
| P11 timing.json | `1b5f156108a4c73f05cb8b2426b266b74a8706da283a3e653d429648c406b5a7` |
| P45 p39_sycl.hpp | `d29e4a9527e7e585ee739dad6726750bfa0f59176fa66a7cde8b2097fa2885c9` |
| P45 p39_fused.hpp | `7d083b68b0f5ff665ed4688c871842bcab6dd5d2386b0516d9da79b8e94740b3` |

The helper also prints hashes for P28/P33/P42 body sources and P39/K2 fixture/selection sources. Source attribution stays with these lab packets and their existing format-data credits. No outside runtime code was adopted.
