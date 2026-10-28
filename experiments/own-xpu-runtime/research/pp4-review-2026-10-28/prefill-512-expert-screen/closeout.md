# 512-row expert operator screen — closeout

<!-- campaign-closeout -->

## Question and identity

Does one512-row bucket+T4 expert dispatch improve enough over two consecutive256-row dispatches to justify engine/wire integration? Eight cases cover IQ2_S, IQ3_XXS, IQ4_NL and Q2_0, two historical layers per family, on B70 card43. Actual admitted SC117 mixed-quant tensor weights and actual native-captured routes from historical **synthetic rank1 inputs** are used; activations are synthetic. These are layers24–47, not current reference-policy stage0. Binary/source/flags and every route identity are retained in the [registration](registration.json) and [build receipt](build-r2-evidence/receipt.json).

## Outcome

**Close this512 expert-only integration lever at its registered materiality threshold.** Weighted routed-family reduction was **7.892480% cold and7.893969% hot**, below the required **>10% in both conditions**. Every case improved at operator scope, but that does not clear the integration decision. No engine/wire change, endpoint speed claim or promotion follows.

All64 physically executed full-output/status gates passed: eight per case covering512/257/511-token extents, separately injected invalid/partial routes, and checks before/after timing. This is operator parity, not whole-engine or independent model fidelity. [Full analysis](run-r1-evidence/analyzed.json.gz), [compact result](run-r1-evidence/summary.json).

## What worked

The same T4/RW arithmetic, bucket and tile kernels processed genuinely adjacent captured route slices without repeating the first256. Timing covered first bucket start through final tile end, including all four baseline kernels versus two candidate kernels. Existing interleaved hot/cold diagnostics and raw samples are retained. Every output word and status matched; CPU support counts predicted fewer tiles but did not substitute for measured timing.

## What failed or remains uncertain

The measured gain missed the registered threshold, so larger production scope is not justified by this screen. Historical synthetic-input routes and synthetic activations limit workload conclusions; current stage0 diagnostic weights guide prioritization only. This result does not reject1024 rows, new routing locality or other kernel mechanisms.

Case index7 initially remained **unlaunched** because case6 postflight reported103,069,515,776 available bytes against103,079,215,104 required—a9,699,328-byte deficit. The coordinator fully byte-verified the completed35,632,128-byte historical routefile into its archive and removed the original; pinned staged slices remained. A new baseline then admitted case7, which completed cleanly. This was admission refusal, not a GPU fault or failed-GPU retry. All eight units returned0 per coordinator; passive final postflight was clean with no holders. User-journal invocation IDs are retained; transient units were already unloaded when read-only `systemctl show` was captured.

## Evidence and patches

- [Retained index](run-r1-evidence/index.json): all case stdout/stderr, launch commands/env, baseline/postflights, archive receipt, exact compiled sources and SHA-verified gzip roundtrips.
- [Unit invocations](run-r1-evidence/units.json), [summary](run-r1-evidence/summary.json).
- [Harness event-span patch](harness-span.patch), [screen source](screen.cpp), [analysis](analyze.py).
- Historical route archive authority: [receipt](run-r1-evidence/route-archive.json.gz); original bytes recover from the listed `.zst`. Raw staged case slices remain under `inputs/`. No archived payload reread was needed for records.
- Initial CPU compile failure and failed header are preserved under `build-r1-evidence/`; corrected CPU build is under `build-r2-evidence/`.

## When to revisit

Revisit only with new material evidence—representative route locality, a materially larger expert fraction or an exact mechanism beyond unchanged T4 occupancy—that justifies the already documented continuation/allocation/wire costs. Keep the current registered production row geometry unchanged and move optimization to the next material lever.
