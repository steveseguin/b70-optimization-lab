# Laguna M12 hybrid expert/N-tile chunk sweep

Date: 2026-08-01 America/Toronto

Status: **closed after the frozen component sweep. All treatments were exact,
all were slower, and no endpoint score was authorized or run.**

## Evidence and question

The protected exact BF16-KV record remains `125.4619731637751 tok/s`. The
packed full-N-major scheduler at `522ca66` proved task ownership and raw BF16
equality, but regressed the stable W13+W2 component by `2.627%`: W13 lost
`1.511%`, W2 lost `4.523%`. Because its one-load descriptor removed the prior
four-int worklist tax, this is direct evidence that full interleave destroys
useful same-expert weight locality.

The opposite endpoint—protected M-major ordering—retains all 32 W13 or 48 W2
N tiles for one expert before moving to the next. Laguna's earlier M8 route
interleave is evidence that some earlier expert exposure can help. The bounded
question is therefore whether a hybrid ordering can retain a block of
same-expert N tiles while exposing other experts early enough to hide latency.

## Frozen treatment

Branch from packed-N-major source `522ca66587f5db288c9d8c6d8db918889c6cc467`
without changing its descriptor format, exact math, persistent pool, or
one-task atomic acquisition.

1. Extend the literal/default-off packed-worklist selector with treatment
   values `4`, `8`, and `16`. Zero is the protected M-major control. Full
   N-major value `1` remains the already closed negative and is not rerun.
2. For chunk `C`, map a logical task to:
   `within = task % C`, `q = task / C`,
   `m_tile = q % tile_count`, and
   `n_tile = (q / tile_count) * C + within`.
   W13's 32 and W2's 48 N tiles are divisible by every frozen C, so there is no
   partial-chunk path.
3. Use one named kernel with uniform power-of-two chunk metadata. Implement
   `% C` and `/ C` as mask/shift so the sweep does not add integer division by
   C. All three treatments carry identical mapping overhead; only locality
   differs.
4. Keep the complete prior fail-closed route and the exact same single packed
   descriptor load. Selector off and all out-of-scope calls remain byte-for-
   byte on the protected scheduler.

## Gates and stop rules

1. **Static gate.** Require the same two DPAS instructions, K32 order, one
   output store, GRF128 mode, no new scratch traffic, one descriptor load, and
   only the expected uniform mask/shift/mapping arithmetic. Prove one-to-one
   ownership for C=4/8/16 on both 51-tile W13 and 57-tile W2 corpora.
2. **Component sweep.** Build one ABI-8 DSO and compare each C independently
   against selector-off from that same ELF. Every arm uses byte-identical
   inputs/descriptors, sentinel-filled outputs, `6/6` raw-BF16 equality, 200
   warmups, and 15 samples of 40 launches. Run all three preregistered arms;
   do not stop after or select by the first result.
3. **Promotion.** No shape may regress more than 1%. Require at least `3%`
   summed speedup for production metadata integration. If more than one arm
   passes, choose the highest preregistered summed median only after all arms
   finish; preserve every result. Approximately `4.7%` component improvement
   is needed to cover the current 130-tok/s gap alone.
4. **Integration/endpoint.** A component pass authorizes only the existing-
   remap, no-extra-launch metadata integration and then a non-scored four-rank
   topology/correctness smoke. A score requires a separate cold first-result
   crossover preregistration.

No model, draft, BF16 KV, teacher, prompt, acceptance, cache-zero, topology,
metric, retry, warmup-generation, reboot, reset, driver, or privileged-recovery
change is authorized. The already-enabled router and DFlash workspace gains
may not be double-counted.

## Result

Source implementation:

- tree: `/home/steve/src/laguna-xpu-kernels-m12-hybrid-nchunk-20260801`;
- branch: `experiment/laguna-m12-hybrid-nchunk-20260801`;
- head: `d7db05849983f26e91cc4dce296806159c8d5f41`;
- source bundle:
  `patches/laguna-s-2.1-xpu-b70/xpu-laguna-m12-hybrid-nchunk-d7db058-20260801.bundle`;
- bundle SHA-256:
  `6d06dd70680b80a536eb5287d21032020840331d8febd336fed206a8fd6a9ee6`;
- bundle prerequisite: `522ca66587f5db288c9d8c6d8db918889c6cc467`.

The selector is fail-closed and accepts only literal `0`, `1`, `4`, `8`, or
`16`. Unset/zero keeps the protected scheduler. Mode 1 reproduces the already
closed full-N-major mapping. Modes 4/8/16 change task ownership only; the
descriptor, tile mainloop, BF16 scale multiplication, DPAS order, and store are
unchanged.

An independent source audit found the host/device argument plumbing correct
and no protected-route change. CPU enumeration proved unique and complete task
ownership for all 12 frozen combinations of tile count 51/57, N-tile count
32/48, and C=4/8/16. The prior full-N-major IGC result still establishes the
same two-DPAS exact mainloop, one descriptor load, one store, GRF128, and no
scratch for the packed kernel family. A new hybrid-specific IGC dump was not
run: it would duplicate the same approximately 18-minute, 107-GB production
compile after the component screen had already closed every mode. Do not cite
this experiment as a fresh hybrid ISA/no-scratch measurement.

The frozen ABI-8 DSO is:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-hybrid-nchunk-build-d7db058-20260801T193423Z/libgrouped_gemm_xe_2.so`

Its SHA-256 is
`cf6979cb144101c288215d60bbd66b484cb02345c555ed6b7bd3ff5eac2f59a9`.
The Intel oneAPI 2025.3.3 build took `1067.50 s`, peaked at `106781940 KiB`
RSS, performed zero swaps, and retained `libsycl.so.8`/`libintlc.so.5`. An
earlier build directory ending `63ca385-20260801T193223Z` is an intentionally
interrupted pre-mask build and contains no candidate DSO.

All arms used one frozen ELF, separate control/treatment processes, identical
input and descriptor hashes, NaN output sentinels, 200 warmups, and 15 samples
of 40 launches:

| C | exact | W13 speedup | W2 speedup | summed speedup | decision |
|---:|---:|---:|---:|---:|---|
| 4 | 6/6 | 0.983713x | 0.983496x | 0.983634x | stop |
| 8 | 6/6 | 0.974085x | 0.993630x | 0.981105x | stop |
| 16 | 6/6 | 0.992139x | 0.990337x | 0.991484x | stop |

Every candidate and control output was fully written. The W13 and W2 packed
descriptor SHA-256 values matched between every control/treatment pair, and
the task-ownership records proved 1632/1632 and 2736/2736 unique tasks.

## Decision and reusable learning

The entire hybrid scheduling family is closed without metadata integration,
four-rank smoke, or endpoint measurement. The protected result remains
`125.4619731637751 tok/s`.

The response across the complete bounded ordering axis is informative:
full N-major C=1 lost 2.627%, C=4 lost 1.637%, C=8 lost 1.889%, C=16 lost
0.852%, and protected full same-expert ordering remains fastest. Recovering
larger same-expert chunks recovers most of the loss but never produces a win.
On this M12 workload, retaining expert-local weight reuse matters more than
earlier cross-expert exposure; do not retry another intermediate chunk size or
an equivalent interleave under a different spelling.

Raw summaries:

- `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-hybrid-nchunk-c4-d7db058-20260801T1955Z/summary.json`;
- `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-hybrid-nchunk-c8-d7db058-20260801T1957Z/summary.json`;
- `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-hybrid-nchunk-c16-d7db058-20260801T1958Z/summary.json`.
