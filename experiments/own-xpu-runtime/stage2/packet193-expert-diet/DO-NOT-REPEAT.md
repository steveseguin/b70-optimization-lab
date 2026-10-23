# Packet193 negative-result index (exact instruction diet of the record expert kernels)

Pending device measurement; no row below is a speed result. The expert-class closures of the kernel-floor study
(`../packet190-record-bundle-k3x/analysis/expert-kernel-study-20261023.md`, section B) and packet192's ledger are carried
so that no closed mechanism is re-tried; 227 `DO-NOT-REPEAT.md` files were grepped on 2026-10-23
(`evidence/do-not-repeat-search.txt`).

| Date | Mechanism | Status | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-17 | geometry sweeps WG64/128, V4/V8/V16, SIMD16, persistent grids (packet53/53b/65/81) | closed: V16 +52 us, persistent +138/+215/+218 us | new register/occupancy evidence with an identical logical tree |
| 2026-10-17 | fewer activation loads / packed input reads (packet81, loads 51->27 / 79->31) | neutral on lane A, exact; revisit = an ALU/latency analysis | packet192 is that analysis; packed reads are not part of this diet (attribution) and remain a separate follow-on |
| 2026-10-18 | E2 scale cache, E3 next-table prefetch into registers, batch2/batch4 lookup, E5 shared activation loads (packet95/102) | closed | a distinct mechanism, not more registers |
| 2026-10-18 | IQ2 grid relocation / compaction (SLM, compact global; packet99/52/53) | closed: 1.24-1.78x slower | - |
| 2026-10-18 | 2D block loads / gate/up tile16 (packet104/104b) | closed: a 10 % micro gain that vanished in the engine | - |
| 2026-10-18 | large GRF / half the resident threads (packet115) | closed: 1.175-1.44x | - |
| 2026-10-18 | warm DOWN bytes in a separate kernel (packet119), kernel-order weight layout (packet142/145), cold/warm 1.22x = streaming cost (packet141) | closed | - |
| 2026-10-19 | 11-bit enumerative / Boolean-circuit IQ2 decoders (packet162/162b), expanded magnitude streams (+3.77 GB/rank) | closed: 4.8x slower on device / does not fit | - |
| 2026-10-19 | dense-weight L2 warm-ahead (packet175, B/A 1.44), D1 scale multicast (packet175b) | closed | - |
| 2026-10-23 | packet192 issue-floor decomposition: gate/up cold 73.75 / warm 46.35 / no-load 44.69 us; down 45.94 / 33.75 / 33.33 | measured: both instruction-issue bound | never as a speed claim; it is this packet's premise |
| 2026-10-23 | **explicit byte-regioned extraction via `std::bit_cast` byte arrays** (brief item ii) | **closed by the ISA gate**: IGC materialises the array (~10 moves per byte); exp-diet 20.5 instr/weight with 4.9 KB spills vs production 15.3; production's shift/mask is already lowered to `:ub` regions (`evidence/isa-rejected/first-pass.md`) | a compiler that does not materialise byte arrays |
| 2026-10-23 | **down-diet hoisted `d*float(level)` products selected by q** (brief's form) | **closed by the ISA gate**: a0 register-indirect moves (258) + 512 B spills at 128 GRF, 1.26x dynamic instructions (`evidence/isa-rejected/down-diet-hoisted-products.asm.gz`); confirms the study's "adds 16 live floats per lane" warning | 256 GRF per kernel qualified separately (packet102/115 rows) |
| 2026-10-23 | decoding all eight chains before the products (`values[8][8]`) | closed: 64 live floats -> 4.9 KB spills; production's eight-live-values order restored | - |
| 2026-10-23 | negating the *product* instead of the decoded weight | not exact: `Inf*0` default-NaN sign is hardware-fixed; the sign is applied to `v` (README 2.2) | - |
| 2026-10-23 | NaN payload order on the Intel host twin for NaN-producing strata (packet162b f2, non-finite-scale banks): 12 rows differ in payload order only; Intel's production also differs from GNU's | recorded, never canonicalised (packet25/54/109 rules); device gate strict | a device payload-order-only kill is a ruling question, not a kernel defect |

Pending rows per candidate (appended by `s193_report.evaluate` after the window): exp-diet, exp-act-epilogue, down-diet
-> qualified (<= 0.85x cold and warm, both orders) / closed / withheld with the measured ratios. A qualified candidate
goes to the exact one-load v5 bracket on the record selection (study C chain of evidence); a closed one is not repeated in
this diet form.

Rules that bind this packet: every claimed byte row must be equal on the device before a timing counts; the kill rules
withhold rather than ratio-correct (packet128 rule); no second process, no reseal after a result exists (packet125 rule);
the epilogue is counted against gate/up + the expsact twin launch.
