# mtp.fc INT4 integration: fresh-cache build + runtime validation result

Date: 2026-08-22. Run root `/home/steve/qwen38-mtpfc-int4-cachebuild-20260822-r1`
(preserved). Driver `run-20260822-qwen38-mtp-fc-int4-cachebuild.sh` (6e94ffd9e),
patch `2659e7d50`, buffers `4fcfae92a`.

## What passed (gates 1, 2, 5)

The default-off vLLM patch, turned ON (`VLLM_XPU_MTP_FC_INT4=1`) on the stock
composite stage with a fresh writable cache, booted and served on GPUs 2,3:

- **Fail-closed buffer load OK**: startup did not refuse; the frozen packed
  buffers loaded and the sha-pinned check passed.
- **Engagement confirmed**: 2 int4 input-dependency markers (per-rank).
- **Fresh door-forked cache built**: namespace `73a5784cca`, distinct from the
  sealed `b99160ae76` - proof the door forks `compile_factors` as designed.
- **Quality battery PASS**: `quality_pass_all=true`,
  `quality_baseline_match_all=true`, `quality_rc=0`. The integration is
  quality-clean against the marginfree quality baseline.
- **Smoke pass**, `cached_tokens_all_zero=true`, MTP5 healthy (mean acceptance
  length 3.82/5 during warmup).

No errors, no traceback, no sha mismatch. The patch is functionally correct
and quality-clean.

## What the rate here is NOT

The runner exited rc=1 on the strict realistic-window metric: `row 6 does not
contain a valid metric window` - the SAME incumbent-lane prompt-6
(`selection--sql-debugging`) stochastic early-EOS that closed the Q64xK32
endpoint series. 22/25 rows produced valid windows; their conventional median
is **31.21 tok/s** (min 29.27, max 31.45).

That 31.2 is NOT the production comparison. This fresh cache compiled without
the marginfree lane's AOT/optimized artifacts (the sealed b99 cache had
`EXPECT_AOT_DIRECT_LOADS=4`), and the incumbent MTP5 lane runs ~101 tok/s.
Acceptance (3.82) and quality (baseline-match) are healthy, so 31.2 reflects
an unoptimized fresh compile, not mtp.fc-op slowness. Absolute rate is not
interpretable across cache identities.

## Remaining: representative A-B

The mtp.fc tok/s verdict requires door-off vs door-on on the SAME
representative config, isolating the op effect:

1. Build the fresh door-on cache with the FULL marginfree compilation config
   (match the incumbent's optimized graph), not the simplified one used here.
2. Handle prompt-6: use the long-KV `ignore_eos` bench channel or a
   prompt-6-robust median (valid-row median with a min-valid-row gate), both
   already built in this repo.
3. Endpoint A-B-B-A: door-off (incumbent ~101 baseline) vs door-on, conventional
   median, bootstrap 95% lower bound > 0 to accept as a speed lever;
   acceptance-rate non-regression; quality battery (already green).

## Equal-config A-B (2026-08-22)

Ran the door-OFF control on the IDENTICAL simplified config (fresh namespace
`7e3affed0c`), isolating the mtp.fc op effect:

- door-OFF (FP16 mtp.fc): conventional median **31.47 tok/s** (23/25 valid)
- door-ON (INT4 mtp.fc): conventional median **31.21 tok/s** (22/25 valid)

Delta **-0.26 tok/s (-0.8%)**, within this config's noise floor (door-OFF min
row 20.33; the metric is bursty under MTP + prompt-6). So the INT4 mtp.fc op
is **neutral vs FP16 at equal config** - no measurable benefit. Both are ~31
because this fresh cache is ~3x off the marginfree production config; the 3x
is the config, not the op (door-OFF is equally slow).

Correction to the build-run note above: the "2 int4 input-dependency markers"
appear in BOTH door states, so they are the lane's other INT4 usage (draft
head, etc.), NOT mtp.fc-specific engagement. The marker count does not confirm
mtp.fc routing; the patch emits no mtp.fc-specific marker. Engagement is
established by the code path + the fail-closed buffer load succeeding, not by
that count.

## Disposition (verdict)

mtp.fc INT4 integration is **functionally validated and quality-clean**
(boots, fail-closed load OK, full quality battery pass with baseline match,
MTP5 acceptance 3.82), and its isolated rate effect is **neutral (-0.8%,
within noise)**. This matches the operator prereg's prediction: mtp.fc is one
small linear called 5x/target-step, so even the ~290 us/step operator saving
is sub-1% end-to-end and cannot be a standalone speed lever.

Recommendation: do NOT promote mtp.fc INT4 as a speed lever. It is a
validated, quality-clean, default-off option that stacks negligibly. A
representative marginfree-config endpoint A-B would need sub-1% measurement
resolution to detect any effect and is low-value unless combined with a
larger lever (e.g. Q64xK32, itself blocked on the chunk-prefill fix). The
patch/buffers/driver remain on record, default-off, for any future stacking
study. The VRAM cost (retained FP16 + packed buffers) argues further against
enabling it for a null rate benefit.
