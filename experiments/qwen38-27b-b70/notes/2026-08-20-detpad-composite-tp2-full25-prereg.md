# Qwen3.8 composite-runtime INT4-pad TP2 full-25 preregistration

Date: 2026-08-20

Status: preregistered; no TP2 GPU arm launched yet.

## Question

The six-arm sealed TP1 diagnostic credited global oneDNN W4A16 prefill
padding for the observed structured-extraction flip. Does the complete
triple-fix runtime (`_xpu_C` SHA `4dd33601...`) with that pad engaged produce
stable full-25 token streams under the production TP2/MTP5 topology, without
changing the sealed graph/AOT cache or losing the established throughput?

This pair is a diagnostic, not a promotion run. The historical target-only A
used the old unpadded `8f11e716...` runtime and was itself only 24/25 stable.
Its quality JSON remains the semantic baseline; its token arrays are a
report-only comparison, not a strict pad-on oracle.

## Frozen identity

- launcher: [`../scripts/run-20260820-detpad-tp2-full25.sh`](../scripts/run-20260820-detpad-tp2-full25.sh), actions `check`, `a`, then `b`;
- exact-native Qwen3.8 AutoRound INT4, GPUs 2,3, TP2, MTP5, FP16, seed 0;
- model manifest SHA `731d851b...`, verified immediately before load through
  complete O_DIRECT and ordinary cached passes;
- composite stage manifest SHA `47861e83...`; native/core/MoE/FA extensions
  `4dd33601...` / `57174764...` / `ea4c20a8...` / `33938cdd...`;
- native GDN on, ReplaySSM speculative path off, persistent scratch on, GDN
  capture on, DDTREE capture flags off;
- INT4 and INT8 completion/input-dependency gates on, target INT4 scope
  `all_target`, target LM head INT8, draft head INT4, both greedy and draft
  fallback margins zero;
- PIECEWISE graph partition capture size 6;
- frozen 25-prompt suite SHA `292dea6a...`, 512 output-token cap, strict
  100-event window, smoke enabled, no trace hooks;
- post-recovery cache root with explicit outer namespace `b99160ae76`, input
  manifest SHA `f3582440...`, tree `723c1599...`, 3,795 entries / 3,246 files /
  395,855,113 bytes;
- expected direct loads: two outer roles (`backbone`, `eagle_head`) and four
  AOT paths (`dc9285...`, `fc5b3...` across ranks 0 and 1);
- expected determinism-pad evidence: exactly one `TORCH_WARN_ONCE` marker from
  each TP rank. Marker cardinality proves per-process branch entry, not the
  number or module ownership of padded GEMMs.

The driver uses an empty environment plus an explicit allowlist. The arm
runner snapshots and hashes the driver, runner, checker, selected wrappers,
suite, peer/reference inputs, and effective native modules before launch. The
post-run gate executes the checker snapshot, not the live source tree.

## Order and stop rules

1. Run `check`. Do not launch if any pinned file/cache/tree/source identity
   differs.
2. Run arm A with quality enabled. Do not start B unless A returns zero and a
   fresh recheck of A passes the same committed checker/driver/repository
   identity.
3. Run arm B with quality disabled and immutable snapshots of A's benchmark
   and the historical target benchmark.

Either arm is a scientific NOGO if any of these occur: nonzero runner status,
model dual-view mismatch, wrong staged path/hash, missing rank pad marker,
wrong/missing/extra direct-load path, graph/AOT compile or save marker,
compile-cache input/output mismatch, incomplete process-group cleanup,
invalid/freshness-failing benchmark, or (for A) semantic quality failure.
Preserve all failed artifacts; do not average their speed.

## Decision criteria

- Pair stability requires complete token-ID array equality on all 25 prompts,
  in frozen order. Text/output hashes are not substitutes.
- Arm A must have `quality_rc=0`, `pass_all=true`, and
  `baseline_match_all=true` against quality baseline SHA `45424f1d...`.
- The checker reports each candidate against historical target A, but that
  comparison is non-blocking. A fresh matched pad-on composite target-only
  oracle is required before promotion.
- Throughput is descriptive until every identity, cache, freshness, pairwise
  token, and quality gate passes. Compare valid arm medians with the honest
  `101.170 tok/s` anchor and the post-recovery descriptive `102.132` /
  `102.176 tok/s` arms.

If A/B is 25/25, next run a matched pad-on target-only oracle before promotion.
If A/B diverges, do not sweep speed flags; return to the first differing
prompt/round with bounded synchronization/localization traces or a TP1
full-25 control.
