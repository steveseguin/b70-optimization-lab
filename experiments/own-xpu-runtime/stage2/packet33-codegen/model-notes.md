# Measured inputs and cost-model limits

All times in this note are historical device event medians, in microseconds. Packet 33 runs no device. Every numeric input is bound to its source file hash and JSON pointer or line in [measurements.json](measurements.json). The model predicts event execution duration, not host launch latency or end-to-end tokens/s.

The primary data come from packet 29 K2. Large GEMVs use eight full-sized rotated regions. Repeated-buffer results, packet 28 aggregates, rounded packet 27 tables and synthetic bounds are retained as explanatory checks and excluded from the primary fit. The two expert gate/up formats stay separate. Multiple matched R5 controls are repeats of one implementation; they must be collapsed before fitting. A count of 200 within one process is not 200 independent compilers, launches of the program, or servers.

| Workload | Implementation | Median us | Matched incumbent us |
| --- | --- | ---: | ---: |
| gdn.recurrence | round2 | 37.6040 | 53.9580 |
| qsa.attention | round2 | 189.6355 | 174.0625 |
| route | round2 | 82.9160 | 66.6660 |
| activation | specialised | 4.7910 | 4.7910 |
| small.hc | round2 | 15.6250 | 32.2925 |
| expsgate.iq2 | p25.half_table | 318.9580 | 175.5210 |
| expsgate.iq3 | p25.half_table | 316.7185 | 175.2080 |
| expsgate.iq2 | p25.paired_input | 215.0000 | 175.6250 |
| expsgate.iq3 | p25.paired_input | 705.4165 | 175.3130 |
| expsgate.iq2 | p25.private_decode | 186.6140 | 175.2090 |
| expsgate.iq3 | p25.private_decode | 188.9580 | 174.8960 |
| expsgate.iq2 | p25.rows4 | 181.3545 | 175.4170 |
| expsgate.iq3 | p25.rows4 | 183.9060 | 175.0000 |
| expsgate.iq2 | p25.wg32 | 181.7710 | 175.4170 |
| expsgate.iq3 | p25.wg32 | 182.2920 | 175.0000 |
| expsgate.iq2 | p27.fp32_input | 190.9895 | 175.4170 |
| expsgate.iq3 | p27.fp32_input | 194.7920 | 174.8960 |
| expsgate.iq2 | p28.paired.rows4 | 85.6250 | 175.1040 |
| expsgate.iq3 | p28.paired.rows4 | 89.2710 | 174.7910 |
| expsgate.iq2 | p28.paired.wg32 | 82.5000 | 175.2080 |
| expsgate.iq3 | p28.paired.wg32 | 84.1670 | 174.7920 |
| expsgate.iq2 | p28.private.rows4 | 109.0630 | 175.1565 |
| expsgate.iq3 | p28.private.rows4 | 113.2290 | 174.8960 |
| expsgate.iq2 | p28.private.wg32 | 103.5410 | 175.2085 |
| expsgate.iq3 | p28.private.wg32 | 109.2710 | 174.8950 |
| expsgate.iq2 | p28.shared.rows4 | 92.5000 | 175.2080 |
| expsgate.iq3 | p28.shared.rows4 | 96.4590 | 174.7920 |
| expsgate.iq2 | p28.shared.wg32 | 89.0620 | 175.2080 |
| expsgate.iq3 | p28.shared.wg32 | 90.9380 | 174.7920 |
| expsdown | p25.private_decode | 120.3120 | 127.3960 |
| expsdown | p25.rows4 | 183.4375 | 127.7090 |
| expsdown | p25.wg32 | 183.0210 | 127.6040 |
| expsdown | p25.wide8 | 156.9790 | 127.4480 |
| expsdown | p27.fp32_input | 182.0840 | 127.5000 |
| expsdown | p27.packed64 | 150.4170 | 127.3960 |
| expsdown | p27.rows2sg | 145.7290 | 127.5000 |
| expsdown | p28.private.rows4 | 165.5210 | 127.5000 |
| expsdown | p28.private.wg32 | 158.3340 | 127.5000 |
| expsdown | p28.shared.rows4 | 165.8330 | 127.3960 |
| expsdown | p28.shared.wg32 | 158.1250 | 127.3960 |
| expsdown | p29.down.rows4 | 123.6460 | 127.3960 |
| expsdown | p29.down.wg32 | 123.4370 | 127.3960 |
| gdn.qkv.q6 | p25.rows4 | 88.2290 | 98.2300 |
| gdn.qkv.q8 | p25.rows4 | 85.5210 | 95.8330 |
| gdn.qkv.q6 | p25.scale8 | 93.6450 | 98.2290 |
| gdn.qkv.q8 | p25.scale8 | 91.3540 | 95.9370 |
| gdn.qkv.q6 | p25.wide8 | 93.5420 | 98.2815 |
| gdn.qkv.q8 | p25.wide8 | 91.3540 | 95.8330 |
| gdn.qkv.q6 | p27.fp32_input | 110.3120 | 100.3130 |
| gdn.qkv.q8 | p27.fp32_input | 107.1870 | 98.2290 |
| gdn.qkv.q6 | p27.packed64 | 95.9370 | 98.2290 |
| gdn.qkv.q8 | p27.packed64 | 93.8540 | 95.7300 |
| gdn.qkv.q6 | p28.dense.rows4 | 80.2080 | 98.1250 |
| gdn.qkv.q8 | p28.dense.rows4 | 75.9370 | 95.7300 |
| gdn.qkv.q6 | p28.dense.wg32 | 75.2090 | 98.2290 |
| gdn.qkv.q8 | p28.dense.wg32 | 72.0830 | 96.3540 |

The expert-down private decoder already reaches 120.312 us, versus its 127.396 us control. This was not dispatched because its gain falls short of the registered 10% admission threshold. It is a better anchor than treating every expert-down candidate as a loss. The p29 forms measure 123.437 and 123.6455 us. A prediction of a few percent improvement cannot establish a new dispatch winner.

The synthetic 71.2 us expert-down figure comes from a different encoding and repeated warm buffers. IQ4_NL uses an 18-byte block with FP16 scale and nonadjacent low/high nibble placement; the stand-in uses a different scale/layout. It omits runtime route/bounds/fallback work. Its simpler arithmetic, data layout and cache state cannot calibrate the same cost coefficients. The real rotated p29 pipeline is the appropriate prediction target.

P29 route totals are 66.666 us for the incumbent and 82.916 us for round2. The event counts are five and three per repetition. The incumbent source is described as four computational stages; the receipt includes another event. Thus “fewer launches” is insufficient: one cannot fit a pure per-launch model to these totals and infer the removed stage was free. QSA is 174.0625 versus 189.6355 us, recurrence 53.958 versus 37.604 us, and small.hc 32.2925 versus 15.625 us in this same summary. The activation reference includes real work; its measured duration is an upper bound on an empty-kernel fixed cost, not a measured host launch constant.

## Proposed identifiable model

Use one observation per workload, implementation and timing mode, with repeated controls collapsed by median. The physical candidate model is `t = fixed × dispatches + a × dynamic memory messages + b × dynamic ALU work + c × dynamic 64-bit work + d × work-items`, using observed SIMD width and real loop trip counts to convert instructions to dynamic counts. Fit no more free terms than this sparse evidence supports. Validate by holding out an entire candidate implementation across shapes and encodings; randomly holding out a duplicate R5 control or IQ2/IQ3 sibling leaks almost the same program into training.

If the extractor supplies only static whole-function counts, fit a labelled surrogate instead of pretending those are instructions per weight. Counts in a loop, cold fallback, unrolled tail and prologue are not equally executed. Static memory-message count also omits coalescing, cache misses, scoreboard pressure and occupancy. Spills, SIMD width, local-memory barriers and stage topology must be exposed separately. No coefficient here can establish causation from these few correlated compiler variants.

Predictions must include held-out error and at least a 10% cross-session variability floor. A prediction interval from residuals is heuristic without new independent measurements. There is no transfer guarantee to another layer, route distribution, device revision, compiler build-option set or runtime.

## Fitted static surrogate (not qualified for reliable prediction)

The available extractor does not establish dynamic instructions per weight. The fitted surrogate therefore uses whole-main-kernel static counts and says so: `log(time / measured R5 workload median)` is regressed on standardized log ratios of SIMD16-equivalent instruction count, memory-message count and 64-bit-operation count, plus extra event count and explicit spill-size KiB. It uses fixed ridge penalty 1. All 72 candidate/workload medians come from the primary p29 JSON; neither the repeated-buffer rows nor the synthetic rows enter. The IQ2 and IQ3 workloads stay separate, and a held-out implementation removes all its encodings and shapes together. Repeated R5 controls supply one median anchor per workload. Source template mappings, assembly hashes, input JSON pointers, coefficients and per-row predictions are in `model.json`; run `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B model.py --fit` to reproduce.

| Model | Training R² | Training RMSE us | Held-candidate R² | Held-candidate RMSE us | Held-candidate MAE us |
| --- | ---: | ---: | ---: | ---: | ---: |
| Static counts, event count | 0.587 | 60.72 | 0.423 | 71.80 | 31.04 |
| Those plus explicit spill size | 0.938 | 23.54 | -0.246 | 105.50 | 32.31 |

Spill size makes the known observations fit much better, but makes held-out squared error worse. This is evidence against using the fitted coefficients as hardware costs. A high training R² is not a successful cost model. The five-feature model's empirical 90th-percentile absolute held-out error is 52.46 us; its worst error is 858.49 us. A ±52.46 us band is only a heuristic covering nine tenths of these held-out points, not a validated confidence interval, and the worst miss is not hidden. The four-feature model has a negative instruction-count coefficient after correlated features are included. Neither model proves fewer instructions cause longer execution.

What the assembly does and does not explain:

- **Paired gate/up:** R5's complete main kernels contain 87/91 static memory messages for IQ2/IQ3. The p28 paired wg32 kernels contain 34, with no barriers versus three in R5. They also contain fewer static SIMD16-equivalent instructions and much less 64-bit work. This is consistent with the observed 82.5/84.167 us results. These are whole-main-kernel counts, not dynamic per-weight traffic.
- **The old paired-input regression:** the IQ2 p25 paired-input assembly declares 2,560 spill bytes and 672 estimated GRF references; IQ3 declares 7,808 spill bytes and 1,816 estimated references. IQ3 has 54 static A32 `load.ugm.d32x32t` versus 13 for IQ2, and 28 corresponding stores versus 11. This supports register-pressure and spill/fill traffic as a mechanism for 215 versus 705.4165 us. The original extractor's zero explicit scratch-message signature was not a no-spill result: A32 UGM block messages carry spills too. The model cannot reliably price a new spilling program when this candidate is held out.
- **packed64 and wide8 down:** both reduce total static memory-message count (78 in R5 to 55), yet measure slower. Packed64 increases static 64-bit operations (264 to 330); wide8 reduces that count to 226 and is still slow. Thus neither total sends nor total 64-bit count explains both losses. Dynamic path frequency, dependencies, shuffle lowering and issue width matter. The no-spill surrogate held-out predictions of 112.44/113.28 us miss the measured 150.417/156.979 us. These candidates are direct counterexamples to selecting by total static instruction count alone.
- **FP32 input:** the recorded time includes a separate conversion/preparation event. Main-kernel static work is not the whole timed job. The saved conversion is cheap relative to the extra dispatch, traffic and remaining generic body. That is a plausible mechanism, not a quantified attribution; this dataset does not isolate each cause.
- **Expanded dense:** R5 gdn.qkv's whole main body contains 32 static memory messages, p28 wg32 12, with barriers removed. That aligns with 98.229 to 75.209 us. Generic R5 handles split and shape branches in one kernel, so the static count includes paths a particular launch does not execute.
- **Route/QSA/recurrence:** a GEMV fit is not a valid predictor for reductions, selection and dependent attention stages. Those measurements are retained, but excluded from regression. The packet18 monolithic `Glue` assembly contains multiple runtime-selected operators; charging its entire function to QSA alone would be false. These families require path-resolved dynamic accounting or coordinator profiling before a numeric cost model can explain their surprises.

The model therefore supports a measurable source→assembly experiment, not a speed claim or a confidently ranked candidate list. Its main useful result is that spills and branch-dependent execution defeat naive static counting. New candidate medians remain predictions pending coordinator timing.

## Independent down path reading

The independent assembly reviewer traced normal finite BF16 full-tile basic-block paths, rather than charging the entire function to each weight. In the hash-matched final O2 dumps, R5 has 475 CFG instruction entries and 25 payload-data messages per eight weights per lane; p29 WG32 has 169 and 15. Input reads change from eight u16 gathers to four d32 gathers, packed-code reads from eight u8 gathers to two d32 gathers, while both still have eight table-byte gathers. These counts are conditional on the review's documented path and exact dump hashes; see [review-assembly.md](review-assembly.md) and its JSON. The independent reviewer verified that the final O2 and initial assembly hashes match. They are not measured cycles, all-input dynamic means, or the final codegen table's static totals.

Despite that large path-count reduction, the historical rotated medians change only from 127.396 to 123.437 us, about 3.1%. This is the clearest reason a count-only model is insufficient. Dependency chains, memory response latency, occupancy and execution masks can dominate an instruction saving; these receipts do not isolate their individual contributions. Both are SIMD32 dispatches. Split SIMD16 qword operations inside one dispatch do not imply two SIMD16 kernel dispatches or twice the useful parallelism. The reviewer also distinguishes declared global private allocation and predicate spills from actual GRF scratch-memory spilling; those quantities must not be merged.

Route and QSA prediction policy: because there is no qualified path-resolved fit, use an explicit no-effect prior on the unchanged source path. The new route rank spelling starts from round2's 82.916 us (R5 incumbent 66.666); the attention specialization starts from round2's 189.6355 us (packet18 incumbent 174.0625). The ranges span the p27/p29 incumbent and round2 observations, enlarged by 10% in each direction: approximately 60.00–92.73 us for route and 156.66–208.60 us for QSA. These are historical-spread priors, not GEMV-model estimates, confidence intervals, guaranteed bounds, or predictions of speedup. `model.json` records the exact source measurement IDs.

## Final source-to-assembly iteration and predictions

The final parser includes `bfn.(...)` instructions, which the first static extraction missed. Its corrected baseline totals agree with the independent reviewer: 2,236 instructions in R5 IQ4 down and 737 in p29 WG32. The fit above and `model.json` use that corrected extraction. The final bank candidate uses explicit packed BF16 source loads to fix the first version's eight-input-message regression. The coordinator's final path review reports 188 instructions and seven payload-data messages per eight weights, versus p29's 169 and fifteen: eight table gathers are gone, at the cost of extra integer work. The initial bank spelling had 231 instructions and eleven messages on its interior tile. All these kernels remain SIMD32; none acquires wider effective dispatch merely from the source rewrite. The final bank assembly has 843 whole-function instructions, so its lower traffic does not mean a smaller whole function.

The following are **unqualified predictions, not measured speeds**. The GEMV estimates come from a fit that fails held-candidate validation; the bands use the empirical 90th-percentile held-out absolute error and are not confidence intervals or guaranteed bounds. The worst held-out error was 858.49 us. Down alone has held-out R² −3.298 and RMSE 44.05 us, so even its apparent candidate ordering is unreliable. Gate predictions can be slower than the previously measured p28 paired kernels; that is further evidence that the surrogate is not a trustworthy local estimator. Zero lower endpoints mean the heuristic error exceeds the predicted time; they do not suggest a physically possible zero-time kernel. The roughly 52 us dense prediction omits an explicit streaming-bandwidth lower bound and may be optimistic.

| Candidate | Workload | Predicted median us | Heuristic interval us | Basis |
| --- | --- | ---: | --- | --- |
| p33.down.bank | expsdown | 63.34 | 10.88–115.80 | Unqualified static surrogate |
| p33.down.select | expsdown | 83.77 | 31.31–136.23 | Unqualified static surrogate |
| p33.gate.restrict | expsgate.iq2 | 107.17 | 54.71–159.63 | Unqualified static surrogate |
| p33.gate.restrict | expsgate.iq3 | 115.81 | 63.35–168.27 | Unqualified static surrogate |
| p33.dense.segment | gdn.qkv.q6 | 51.96 | 0.00–104.42 | Unqualified static surrogate |
| p33.dense.segment | gdn.qkv.q8 | 50.69 | 0.00–103.15 | Unqualified static surrogate |
| p33.dense.segment | qsa.k | 10.52 | 0.00–62.98 | Unqualified static surrogate |
| p33.route.rank4 | route | 82.92 | 60.00–92.73 | Source-path no-effect prior |
| p33.qsa.shape | qsa.attention | 189.64 | 156.66–208.60 | Source-path no-effect prior |

The fixed-shape QSA candidate is compiled as a separate `Kernel<Op, Stage, true>` specialization, not a runtime branch inside a mixed-shape kernel. That establishes distinct generated code, not its speed. The route/QSA numbers remain source-path priors until the coordinator runs the prepared harness. No device ran in packet 33.
