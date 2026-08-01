# Laguna M12 hybrid expert/N-tile chunk sweep

Date: 2026-08-01 America/Toronto

Status: **preregistered before hybrid source implementation or device
execution. No endpoint score is authorized.**

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
