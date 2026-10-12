# Packet33 — generated-code study, CPU only

Offline dumps worked. The24 SPIR-V modules from a relink of packet29's original
objects occur **byte for byte in its shipped executable**. ocloc compiled the
requested images for B70 PCI0xe223 revision0 with precise divide/sqrt retained.
All330 selected GEN dumps match their final offline ELF text; three discarded
IGC attempts are retained separately. No device discovery or device program ran.

The useful down candidate removes eight of15 repeated data messages per octet,
but adds19 instructions. The fitted model does **not** predict held-out candidates
reliably. All candidate timings below are unqualified predictions, not speeds.
K0 and K2 are compiled and prepared for the coordinator, not executed.

## Method and scope

`link-command.json` records the original packet29 objects and exact link flags,
including `-foffload-fp32-prec-div -foffload-fp32-prec-sqrt`, with only the output
path and `-fsycl-dump-device-code` instrumentation changed. `modules.json` records
entry names, specialization constants, execution modes, sizes, hashes and offsets
inside the old shipped binary. `offline.py` re-extracts those exact bytes.
This is stronger identity evidence than a same-name source recompilation.

ocloc26.18 accepts `-device 0xe223 -revision_id 0` and API options
`-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt`. Only its process receives
`IGC_ShaderDumpEnable=1`, `IGC_DumpToCustomDir=...`, and
`IGC_ShowFullVectorsInShaderDumps=1`. GEN, vISA, LLVM and zeinfo stay under ignored
build/. [Runtime option evidence](runtime-options.md) records installed-library
hashes and pinned UR/SYCL/NEO translation sources. Runtime `-ze-opt-level=2`
becomes IGC `...=O2`; the precise offload flags imply the correctly rounded option.
Product defaults (>4GB, bindless, cache controls) are retained. No runtime JIT
trace was taken, so exact agreement with all internal flags from an old on-card
run is **unconfirmed**. We prove shipped SPIR-V and final offline GEN identity,
not historical driver-JIT byte identity.

`analyze.py` counts instruction opcodes including BFN, SIMD widths, LSC message
mnemonics/element/address widths, typed64-bit operations, conversions, indirect
register moves, barriers/SLM, calls, payload and private/scratch metadata. Its
backedge regions are lexical regions, not a dynamic CFG execution count.
It matches .dat instruction bytes to final .progbin ELF.text plus zero padding
before selecting an IGC attempt. No uninlined call instruction was found.

## Per-kernel census

The table below is the53-row requested study, with type/split variants separated.
[codegen.json](codegen.json) holds every member kernel and memory-message histogram,
assembly hash, backedge region, payload and spill/private/scratch evidence.
Static totals include cold, exceptional and alternate branches. Multi-kernel
rows sum distinct instantiations; they are not all launched together. All these
study entries use SIMD32. SIMD16 halves of64-bit instructions are **not** two
SIMD16 subgroup dispatches. The reduction tree is independently traced only
where the source requires it; generic operations have their own reductions.

`64-bit typed inst` includes moves and integer instructions with qword operands,
not just address calculation. `int→float` is a syntactic conversion count:
BF16 expansion itself is integer shift/bit reinterpretation, while half decode
has integer IEEE/subnormal handling. `Pre-branch` is a static prefix, **not a
measured launch cost**. Scratch/private bytes use zeinfo hardware-thread units;
per-lane buffer metadata remains in JSON. Spill size and allocation size are not
additive. Flags can spill into GRFs without data scratch messages.

Most dynamic per-weight/per-work-item counts are **unestablished**. We did not
replace them with whole-function instructions divided by K. The separately
reviewed finite, full-octet down paths provide real conditional CFG sums:
R5 475inst/25messages, p29.wg32 169/15, bank188/7 per eight active-lane weights,
i.e.59.375/3.125,21.125/1.875,23.5/0.875 per weight for that path. At K640 each
lane has two full octets and lanes0–15 have a third; payload, first-tile setup,
invalid routes and final reduction must be counted separately. These numbers
are SIMD instruction/control-flow counts, not issue cycles or memory transactions.

| Kernel | SIMD | Static inst / messages | 64-bit typed inst | int→float | SLM / barrier | Spill B | Scratch B/HW thread | Private B/HW thread | Cross-thread payload B | Pre-branch inst / backedges | Inner inst / messages per 8 lane weights |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| down R5 IQ4 | 32 | 2236 / 78 | 264 | 54 | 2 / 3 | 0 | 0 | 5888 | 196 | 69 / 18 | 475 / 25 |
| down p25.private_decode | 32 | 1969 / 83 | 258 | 55 | 6 / 3 | 0 | 0 | 256 | 160 | 23 / 11 | unestablished |
| down p27.packed64 | 32 | 1895 / 55 | 330 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 4 | unestablished |
| down p25.wide8 | 32 | 1572 / 55 | 226 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 4 | unestablished |
| down p27.fp32_input | 32 | 2053 / 83 | 246 | 55 | 6 / 3 | 0 | 0 | 256 | 160 | 23 / 11 | unestablished |
| down p28.shared.wg32 | 32 | 966 / 63 | 140 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| down p29.wg32 | 32 | 737 / 51 | 83 | 24 | 0 / 0 | 0 | 0 | 0 | 56 | 24 / 3 | 169 / 15 |
| down p29.rows4 | 32 | 738 / 51 | 83 | 24 | 0 / 0 | 0 | 0 | 0 | 56 | 25 / 3 | unestablished |
| gate R5 IQ2 | 32 | 2686 / 87 | 363 | 71 | 2 / 3 | 0 | 0 | 5888 | 196 | 70 / 18 | unestablished |
| gate p28.private.wg32 IQ2 | 32 | 1796 / 76 | 156 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.shared.wg32 IQ2 | 32 | 1640 / 60 | 100 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.paired.wg32 IQ2 | 32 | 982 / 34 | 73 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| gate p25.half_table IQ2 | 32 | 2799 / 202 | 437 | 64 | 6 / 3 | 1728 | 2048 | 256 | 160 | 31 / 10 | unestablished |
| gate p25.paired_input IQ2 | 32 | 2716 / 184 | 364 | 72 | 6 / 3 | 2560 | 4096 | 256 | 160 | 33 / 11 | unestablished |
| gate R5 IQ3 | 32 | 2702 / 91 | 374 | 79 | 2 / 3 | 0 | 0 | 5888 | 196 | 69 / 18 | unestablished |
| gate p28.private.wg32 IQ3 | 32 | 1879 / 76 | 181 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.shared.wg32 IQ3 | 32 | 1724 / 60 | 125 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.paired.wg32 IQ3 | 32 | 1032 / 34 | 88 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| gate p25.half_table IQ3 | 32 | 2773 / 192 | 435 | 72 | 6 / 3 | 2048 | 2048 | 256 | 160 | 31 / 10 | unestablished |
| gate p25.paired_input IQ3 | 32 | 2965 / 270 | 377 | 80 | 6 / 3 | 7808 | 8192 | 256 | 160 | 33 / 11 | unestablished |
| dense R5 SG32/split4 Q6 | 32 | 1151 / 32 | 129 | 46 | 2 / 3 | 0 | 0 | 0 | 81 | 14 / 8 | unestablished |
| dense p28.wg32 Q6 split1 | 32 | 353 / 12 | 32 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 2 | unestablished |
| dense p28.wg32 Q6 split4 | 32 | 353 / 12 | 33 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 20 / 2 | unestablished |
| dense p28.rows4 Q6 split1 | 32 | 420 / 14 | 42 | 12 | 0 / 3 | 0 | 0 | 0 | 120 | 18 / 2 | unestablished |
| dense p28.rows4 Q6 split4 | 32 | 467 / 18 | 43 | 12 | 4 / 3 | 0 | 0 | 0 | 128 | 21 / 2 | unestablished |
| dense p25.scale8 Q6 | 32 | 1411 / 39 | 192 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 2 | unestablished |
| dense R5 SG32/split4 Q8 | 32 | 1151 / 32 | 129 | 46 | 2 / 3 | 0 | 0 | 0 | 81 | 14 / 8 | unestablished |
| dense p28.wg32 Q8 split1 | 32 | 353 / 12 | 32 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 2 | unestablished |
| dense p28.wg32 Q8 split4 | 32 | 353 / 12 | 33 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 20 / 2 | unestablished |
| dense p28.rows4 Q8 split1 | 32 | 420 / 14 | 42 | 12 | 0 / 3 | 0 | 0 | 0 | 120 | 18 / 2 | unestablished |
| dense p28.rows4 Q8 split4 | 32 | 467 / 18 | 43 | 12 | 4 / 3 | 0 | 0 | 0 | 128 | 21 / 2 | unestablished |
| dense p25.scale8 Q8 | 32 | 1411 / 39 | 192 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 2 | unestablished |
| route specialised (5 stages) | 32 | 4749 / 384 | 530 | 83 | 0 / 0 | 0 | 32768 | 22528 | 768 | 858 / 1 | unestablished |
| route round2 (3 stages) | 32 | 5231 / 469 | 378 | 8 | 128 / 150 | 0 | 0 | 0 | 88 | 96 / 8 | unestablished |
| QSA packet18 / activation / GDN native fixture | 32 | 12241 / 513 | 612 | 229 | 122 / 180 | 0 | 32768 | 21504 | 204 | 52 / 85 | unestablished |
| QSA/GDN packet18 production adapter | 32 | 29282 / 1643 | 4275 | 1055 | 167 / 228 | 0 | 65536 | 45312 | 772 | 184 / 155 | unestablished |
| round2 score | 32 | 547 / 87 | 19 | 18 | 40 / 36 | 0 | 0 | 0 | 192 | 16 / 1 | unestablished |
| round2 softmax | 32 | 754 / 41 | 19 | 13 | 9 / 21 | 0 | 0 | 0 | 192 | 18 / 5 | unestablished |
| round2 value | 32 | 735 / 34 | 22 | 13 | 7 / 15 | 0 | 0 | 0 | 192 | 18 / 4 | unestablished |
| round2 GDN recurrence | 32 | 2825 / 24 | 35 | 17 | 0 / 0 | 0 | 0 | 0 | 184 | 14 / 1 | unestablished |
| small.hc | 32 | 1147 / 62 | 222 | 8 | 4 / 6 | 0 | 0 | 0 | 80 | 8 / 1 | unestablished |
| NEW down.bank | 32 | 843 / 27 | 40 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | 188 / 7 |
| NEW down.select | 32 | 1757 / 57 | 138 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | [290, 306, 482] / 17 |
| NEW gate.restrict IQ2 | 32 | 926 / 34 | 68 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | unestablished |
| NEW gate.restrict IQ3 | 32 | 977 / 34 | 83 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | unestablished |
| NEW dense.segment Q6 split1 | 32 | 318 / 13 | 15 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 1 | unestablished |
| NEW dense.segment Q6 split4 | 32 | 406 / 23 | 57 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 14 / 0 | unestablished |
| NEW dense.segment Q8 split1 | 32 | 318 / 13 | 15 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 1 | unestablished |
| NEW dense.segment Q8 split4 | 32 | 406 / 23 | 57 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 14 / 0 | unestablished |
| NEW route.rank4 | 32 | 3051 / 349 | 138 | 8 | 128 / 150 | 0 | 0 | 0 | 88 | 96 / 8 | unestablished |
| NEW QSA.shape score | 32 | 465 / 87 | 19 | 0 | 40 / 36 | 0 | 0 | 0 | 200 | 16 / 1 | unestablished |
| NEW QSA.shape softmax | 32 | 733 / 42 | 19 | 13 | 9 / 21 | 0 | 0 | 0 | 200 | 18 / 5 | unestablished |
| NEW QSA.shape value | 32 | 722 / 34 | 22 | 13 | 7 / 15 | 0 | 0 | 0 | 200 | 18 / 4 | unestablished |


## What explains the surprises

- **Down:** R5's finite octet has eight code-byte, eight table-byte, eight input
  u16 and one scale-u16 gathers. p29 packs the code/input loads, leaving two
  code-d32, four input-d32, eight table-u8 and one scale-u16 gathers. The new bank
  removes the eight table gathers. Address math remains A64: qword adds fall
  from24 to8 in the reviewed p29/new octet. Absolute64-bit pointers were not
  falsely advertised as A32 because source offsets are32-bit.
- **Packed64/wide8/fp32_input:** fewer whole-function instructions did not make
  these faster. Their static64-bit, SLM/barrier, input/preparation and launch
  footprints differ. fp32_input has an extra conversion preparation stage and
  more input traffic. Packed64 keeps more typed64-bit operations than R5.
  These are plausible mechanisms; the failed held-out fit cannot establish a
  quantitative causal explanation for every loss or p29's small measured gain.
- **Paired gate:** p28.paired's IQ2 main body has982 instructions/34 messages
  versus private1796/76 and shared1640/60. Reusing paired decode and addressing
  is a large code change consistent with the measured win. p25.paired_input
  instead spills2560bytes IQ2 and7808bytes IQ3, with many transposed A32 UGM
  spill/fill messages; private_size alone must not be called a spill.
- **Dense:** specialised p28 removes general paths/SLM and has353 main-body
  instructions versus R5's1151, consistent with the measured98→75us change.
  The new fixed segment reduces353→318, but messages rise12→13; this is not a
  justified promise of a further speedup. Split4 still needs its finish event.
- **Route:** the receipt/source baseline has **five**, not four, stages. Three
  launches did not guarantee a win: rank/control/SLM work matters. The new
  four-at-once rank loop cuts the aggregate static code5231→3051 but leaves
  barriers and three stages. A data-dependent rank cost is not fit by GEMV.
- **QSA/GDN/activation:** original entry points share large runtime switches.
  Their full assembly sizes cannot identify a tiny activation launch floor.
  Round2 specialised paths expose the relevant loops; fixed QSA score constants
  reduce547→465 instructions, softmax754→733, value735→722, with unchanged
  barriers. No fixed launch latency is inferred from payload size.
- **Synthetic71us:** the4-bit/table stand-in is not the exact IQ4 scale/decode,
  input, descriptor, rounding and reduction workload. It supplies no matched
  quality or traffic gate. It is recorded as diagnostic and excluded from fitting.

[Independent down reading](review-assembly.md), [candidate reading](review-candidate-assembly.md)
and [short excerpts](assembly-excerpts.md) preserve the path evidence.

## Cost model and measured inputs

All historical inputs have file hashes and JSON pointers/line sources in
[measurements.json](measurements.json). [model-notes.md](model-notes.md) lists each
fitted median and its source file from the supplied p29,p28,p27 receipts; no new
on-card number was created. There are359 extracted rows,154 primary JSON rows,
and72 mapped candidate/workload fit rows. The71us synthetic diagnostic is not a
fit point. Duplicate receipt views and reread large buffers are not independent
training samples.

The predeclared ridge surrogate is
`log(t / matched R5 median) = intercept + beta · standardized features`.
Features are log ratios of SIMD16-equivalent static instruction counts, data
messages and typed64-bit instructions, plus extra events and spill KiB. Weight
count/effective width is controlled by matching each workload, not by assuming
all kernels share a universal nanoseconds-per-weight constant.

Training R²0.938, RMSE23.54us, MAE16.16us. Leave-candidate-out R²**-0.246**,
RMSE105.50us, MAE32.31us, worst error858.49us. Down-only held-out R²-3.298.
Removing spill gives held-outR²0.423/RMSE71.80us while degrading training; that
ablation exposes overfit rather than rescuing a validated predictor. Coefficients
are collinear and some signs are physically implausible. No causal per-load
latency is claimed. Missing factors include dynamic paths, cache/transaction
coalescing, live-register occupancy, scheduling and control-vs-control drift.

## Candidates and unqualified predictions

All candidates keep BF16 input/output, weights, serial multiply/add order,
rounding and the exact required reduction tree. See [source contracts](candidates-notes.md),
[candidates.hpp](candidates.hpp), [submission](p33_submit.cpp) and deterministic
[route/QSA generation](build_driver.py). Independent identity review found no
remaining finite-source defect. No floating-point option was relaxed.

The source→assembly loop is recorded by iteration1.patch and the independent
assembly reviews. Initial down.bank still used11 messages and231 instructions
per octet; explicit complete vec8 reads reached7/188. Down.select is a rejected
mechanism: it became divergent branches and17 messages/290–482 instructions.
It stays in the prepared diagnostic specifically because the weak fit predicts
it too favorably. Gate restrict reduces IQ2 982→926 and IQ3 1032→977 static
instructions, with34 messages unchanged. No extra barrier was introduced.

The following are **predictions, not measurements**. GEMV intervals use the
held-out p90 absolute error (52.46us), not confidence intervals. The858us worst
error is outside them. Zero lower ends are unphysical and show a missing
bandwidth floor. Route/QSA numbers are historical null-effect priors with a
widened span, not outputs of a fitted dynamic model.

| Candidate / workload | Predicted median us | Heuristic range us | Decision |
|---|---:|---:|---|
| p33.down.bank / expsdown | 63.34 | 10.88–115.80 | unmeasured; coordinator gate pending |
| p33.down.select / expsdown | 83.77 | 31.31–136.23 | negative assembly diagnostic |
| p33.gate.restrict / expsgate.iq2 | 107.17 | 54.71–159.63 | unmeasured; coordinator gate pending |
| p33.gate.restrict / expsgate.iq3 | 115.81 | 63.35–168.27 | unmeasured; coordinator gate pending |
| p33.dense.segment / gdn.qkv.q6 | 51.96 | 0.00–104.42 | unmeasured; coordinator gate pending |
| p33.dense.segment / gdn.qkv.q8 | 50.69 | 0.00–103.15 | unmeasured; coordinator gate pending |
| p33.dense.segment / qsa.k | 10.52 | 0.00–62.98 | unmeasured; coordinator gate pending |
| p33.route.rank4 / route | 82.92 | 60.00–92.73 | unmeasured; coordinator gate pending |
| p33.qsa.shape / qsa.attention | 189.64 | 156.66–208.60 | unmeasured; coordinator gate pending |

## Arithmetic-preserving options

[option-study.json](option-study.json) recompiles the same p29 SPIR-V. Default
wg32/rows4 are737/738 static instructions,51messages,128GRFs. Requesting256GRFs
produces735/736instructions,51messages: no convincing mechanism improvement.
Disabling backend optimisation produces318/320instructions,13messages and128GRFs
because unrolling/control structure differs; static shrinkage is not a speed
prediction. Precise division/sqrt remains enabled in both experiments. The
256GRF option is accepted by ocloc; forwarding through this installed runtime
was not tested. Backend opt-disable has a documented Level Zero translation.
Frontend O1/O2/O3 metadata maps to the same backendO2; frontend variants were
not separately benchmarked or declared equivalent.

Restrict/noalias and32-bit bounded offsets were tested in the candidate source
and their actual effect is in the census. Required subgroup32 stays32; changing
it would require preserving the32-lane arithmetic tree and a fresh identity gate.
No fast math, reassociation, approximate reciprocal, denormal or precision change
is an optimization candidate here.

## Gates, artifacts and next boundary

Four fresh host processes (two g++, two icpx), each3,442,552 required checks,
pass with zero required failures and matching required finite fingerprints.
That is13,770,208 required checks total. Each process additionally records283,520
exception diagnostics;652 expert-vs-R5 nonfinite differences remain unqualified.
Historical3-token QSA expected bytes differ at two positions from the current
reference; that unchanged-core discrepancy is diagnostic, not silently tolerated.
The device-only vec8 load branch is source-reviewed/offline-compiled, **not**
executed by the CPU scalar fallback. CPU checks cover odd lengths, actualK2560,
split4/nonzero ranges, full route tuples, current reference fixtures, NaN policy
and fresh-process identity. [Gate receipt](candidate-gates.json),
[independent identity review](review-identity.md). The strict receipt aggregator
passes13 CPU protocol tests. ldd resolves all native dependencies.

The sealed native binaries have never run:

- `p33-k0`: `2423d4d685de900f40329d6187298d63dba5142ff479dbf378bf0b3f15c89820`
- `p33-timing`: `3179b6952979361253364b1a50079eb5e0a84645343042c1e448e6e607585daf`

CPU binary hashes:

- `candidate-cpu-gcc`: `233bc6ea7f3b6c4ef27b4ad2f04c402c8ae863eebd38683033d2d05b884a0249`
- `candidate-cpu-icpx`: `c20e8439cb5ea75d5f695c5470e5b3c52e299026b3f0117418513dcb5020f321`

[WINDOW.md](WINDOW.md) contains the exact K0 then K2 commands, environment,
expected durations and300/720second watchdogs. [INTEGRATE.md](INTEGRATE.md)
defines packet26 dispatch vocabulary and the unmodified-runtime admission
boundary. [REBUILD.md](REBUILD.md) records CPU-only reproduction and the >1MiB
extracted-evidence retention reason. [build-receipt.json](build-receipt.json)
seals local sources,25 external objects, binaries and gates.

Remaining analysis scope is explicit: many variable kernels lack exhaustive
dynamic per-weight counts; no independent activation launch floor or transferable
accurate cost model was established. No candidate is device-qualified and no
speed record or existing dispatch was changed. Scratch downloads/temp directories
were deleted; retained binaries/dumps are ignored evidence required for the
coordinator and inspection. [Closeout](CLOSEOUT.md), [do not repeat](DO-NOT-REPEAT.md).
