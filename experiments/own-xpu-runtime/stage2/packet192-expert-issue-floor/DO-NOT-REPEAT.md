# Packet192 negative-result index (expert-kernel issue floor)

Measured 2026-10-23 (see the row); no row below is a speed result. The expert-class closures carried from the
expert kernel-floor study of 2026-10-23 (`../packet190-record-bundle-k3x/analysis/expert-kernel-study-20261023.md`,
section B; 226 DO-NOT-REPEAT files grepped again on 2026-10-23 for `prefetch|issue|no-load|alias|warm|expert`)
are listed so that a follow-on packet does not reopen them.

| Date | Measurement / mechanism | Status | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-23 | **packet192 issue-floor decomposition** of `p90exp::Kernel<IQ2_S,2560,WG64,wide>` and `p100::Kernel<2>`: cold (384 real routes, 512 MiB scrub) / L2-warm / no-load (aliased slab) | **Measured 2026-10-23 (lane B, card 2, lanequeue-B38, 03:33-03:34 UTC, 34 s on device): both kernels instruction-issue bound.** gate/up cold 73.75 / warm 46.35 / no-load 44.69 µs (warm/cold 0.629, no-load/warm 0.964); down cold 45.94 / warm 33.75 / no-load 33.33 (0.735, 0.988); layer-equivalent cold 119.69 µs vs the 37.36 µs copy floor; no kill rule fired; cross-checks vs packet100b/162b within tolerance. Follow-on bars (≤ 0.85× production in both strata): exp-diet cold 62.69 / warm 39.40; exp-act-epilogue cold 67.29 / warm 44.01 (kernel + expsact launch); down-diet cold 39.05 / warm 28.69 → packet193. Evidence `evidence/issue-floor-B1/`. | never repeat as a speed claim; a repeat needs a different kernel pair or a new stratum |
| 2026-10-17 | geometry sweeps WG64/128, V4/V8/V16, SIMD16, persistent grids (packet53/53b/65/81) | closed: V16 +52 us, persistent +138/+215/+218 us | new register/occupancy evidence with an identical logical tree |
| 2026-10-17 | fewer activation loads (packet81, loads 51->27 / 79->31) | neutral on lane A, exact: "expert limiter is not load issue"; revisit condition is exactly an ALU/latency analysis | this measurement is that analysis; a diet brief may cite it |
| 2026-10-18 | E2 effective-scale cache (packet95), E3 next-table prefetch into registers (packet95, -0.46 %), batch2/batch4 lookup (packet102, 0.981/1.002), E5 shared activation loads (1.033x) | closed | a distinct mechanism, not more registers |
| 2026-10-18 | IQ2 grid relocation / compaction: SLM, compact global, compact+halfcache (packet99; packet52/53) | closed: 1.24-1.78x slower | - |
| 2026-10-18 | 2D block loads / tile16 layout for gate/up (packet104/104b: micro 0.893-0.898, engine 0 / -0.35 %) | closed: a 10 % micro gain that vanished in the engine | - |
| 2026-10-18 | large GRF / half the resident threads (packet115: 1.175x-1.44x) | closed | - |
| 2026-10-18 | warm the DOWN bytes in a separate kernel (packet119: 1.079x), kernel-order weight layout (packet142/145: null), cold/warm 1.22x is streaming cost (packet141) | closed | - |
| 2026-10-19 | 11-bit enumerative / Boolean-circuit IQ2 decoders (packet162/162b: 4.8x slower on device), expanded magnitude streams (+3.77 GB/rank does not fit) | closed | - |
| 2026-10-19 | dense-weight L2 warm-ahead (packet175: B/A 1.44, "any variant that reads the weights twice is dead"), D1 scale multicast (packet175b) | closed | - |
| 2026-10-23 | naive gate/up/down fusion (no grid barrier), batching ten experts (already production), activation epilogue inside the split-stream gate/up (packet65 "skipped", open per study B iii'') | fusion closed; epilogue open, unmeasured (4-5 us ceiling) | only as `exp-act-epilogue` after this measurement |

Rules that bind this packet: the no-load stratum is `diagnostic_only` and `exactness_claim: false`, excluded from
every exactness statement; cold/warm bytes must equal the host-twin fixtures on all 384 routes before timing
counts; a kill rule withholds the whole verdict (never ratio-corrected, packet128 rule); no second process, no
reseal after a result exists (packet125 rule).

## Packet192 device measurement

| Date | Measurement | Result | Follow-on |
| --- | --- | --- | --- |
| 2026-10-23 | packet192 issue-floor measurement (record gate/up + down kernels; cold/warm/no-load) | measured; gate/up: instruction-issue bound: only an instruction diet can move the class; down: instruction-issue bound: only an instruction diet can move the class; evidence `issue-floor-B1/analysis.json` | per the study C: diet / LSC-prefetch candidate only as the verdict names; never a speed claim |
