# Qwen3.8 b2dd/1e90 TP4 zero-overlay R1 recovery

Date: 2026-08-25 UTC

R1 completed its hardware gate and all three model arms. Diagnostic measured
`72.07605937552125 tok/s`; strict natural-EOS A/B measured
`71.77179128057259 / 71.82969607434323 tok/s`. Strict A passed the complete
quality battery, both strict arms cleared the frozen per-arm floor, and the
pair cleared the one-arm floor. The zero-overlay frozen snapshot is therefore
a qualified dated TP4 anchor.

The outer wrapper still exited 2 at `stage=aggregate`. This was not a model,
quality, cache, or speed failure: mawk reserves `floor` as a built-in, so the
wrapper's deterministic `awk -v floor=...` threshold calculation was a syntax
error after replay B had already passed and cleaned up. The emergency manifest
then could not read several root-owned compile-cache files as the unprivileged
user. The original failed `final.status` remains untouched.

Offline recovery was deliberately limited to revalidating the sealed hardware
and input manifests, all three arm identities and 25-row benchmarks, all three
exact/cache-zero canaries, the strict-A 7/7 exact + 8/8 one-hash repeat + 8K
needle + 24/24 baseline + 16/16 cache-zero battery, and byte-identical cache
manifests. It then evaluated the preregistered numeric comparisons and wrote a
separate `recovered-result.json`. No model arm was rerun and no observation was
edited.

The recovered result SHA-256 is
`d4d94a33161171461155e8526b53b306a38ec99f978b41d53912ce9c9e3b4201`.
The complete privilege-aware recovered campaign manifest SHA-256 is
`d94f843161a603005b6fb0011fc5ad3105fea38736ca760f35c87762f327353e`.
The structured tracked closeout is
`data/2026-08-25-qwen38-b2dd9ce73d-tp4-zero-overlay-r1-recovery.json`.

The tracked wrapper now avoids mawk's reserved name and writes future campaign
manifests through the same privileged read path used for cache manifests. The
exact launched wrapper remains frozen in commit `a5224cb30` and in R1's sealed
`inputs/` directory.

This result does not lower or replace any historical value and did not apply
the accepted 152-decision TP4 overlay. The prior stock strict
`71.9001988117144 tok/s` capture remains the higher observation, so this run
does not automatically trigger a LocalMaxxing submission. Its product value is
closing the b2dd/1e90 TP4 blank with a replicated, quality-certified source
stack measurement.
