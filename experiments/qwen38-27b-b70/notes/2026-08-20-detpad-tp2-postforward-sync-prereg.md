# Qwen3.8 sealed TP2 post-forward synchronization preregistration

Date: 2026-08-20

Status: **completed; S1 failed the primary endpoint and S2 is forbidden**.

## Question

C1 reproduced A2's catastrophic 512-zero prompt-24 stream under the exact
sealed pad-on TP2/MTP5 identity. Does a rank-local XPU synchronization
immediately after each target/verifier model forward and before postprocessing
remove that active variability when the entire 25-request history is retained?

This is a diagnostic boundary intervention, not a performance arm and not a
candidate fix. It changes execution order on both TP ranks after the primary
model forward. Even a positive result localizes only to forward-completion or
visibility timing before postprocessing; it does not identify oneCCL, a
specific layer, target versus draft, or the underlying faulty operation.

## Frozen design

Driver:
[`../scripts/run-20260820-detpad-tp2-postforward-sync.sh`](../scripts/run-20260820-detpad-tp2-postforward-sync.sh)

S1 and any authorized S2 retain C1's full identity and request order:

- GPUs 2,3, TP2, native MTP5, FP16, seed 0, margins zero;
- complete `4dd33601...` composite with graph-safe FA `33938cdd...`;
- global oneDNN W4A16 pad on and one pad marker required per TP rank;
- native GDN on, ReplaySSM speculative path off, persistent scratch on;
- sealed b991 graph/AOT cache, direct loads only, byte-identical postflight;
- frozen full-25 suite with smoke and fresh/cached-zero gates;
- packet trace, layer trace, and replay microscope off;
- `VALIDATION_SYNC_AFTER_MODEL_FORWARD=1` and the sealed expected identity set
  to `1`.

The common runner records the effective flag, and the post-run checker requires
both effective and expected values to equal one. With the pinned source, each
successful XPU target/verifier forward takes the synchronization branch before
postprocessing on both TP ranks. The later MTP drafter does not traverse this
hook; its timing is affected only downstream. This is source-execution
engagement rather than a per-call marker; the completed 25-prompt service and
per-rank pad markers are required alongside it.

C1's checksum set and frozen environment are pinned before either launch. S1
uses sane B2 as a report-only reference and has no peer-parity requirement.
S2, if authorized, uses S1 as its mandatory complete-token peer and B2 as the
report-only reference. Before S2, the operator must independently calculate
S1's `SHA256SUMS.pre-manifest` SHA-256 and supply it as the second driver
argument. The driver verifies that manifest before checking its contents and
records the independent SHA in S2's identity; it never derives the expected
value from the manifest it is validating.

## Endpoints and stop rules

Primary endpoint: prompt 24
`holdout--long-rollover-repository-audit`.

- corrupt A2/C1 family: 512 zeros, output SHA `aeb1da71...`;
- sane B2 family: begins `71093,13102,198`, output SHA `c923f52f...`.

Secondary endpoints are the three-family SQL prompt at index 6 and factual
prompt at index 11. Always compare complete token-ID arrays.

1. Stop on any ordinary model, runtime, pad, cache, direct-load, freshness,
   cleanup, or checker failure.
2. If S1 prompt 24 is corrupt or differs from sane B2, stop. The broad
   completion boundary is insufficient; proceed to the request-filtered
   prompt-24 replay microscope.
3. If S1 prompt 24 exactly matches B2, run exactly one S2 arm.
4. A strong positive diagnostic requires S1/S2 25/25 mutual equality and sane
   prompt-24 equality to B2. This supports a forward-completion/order boundary
   cause but is not lane-wide determinism or promotion evidence.
5. If S1/S2 differ anywhere, or S2 prompt 24 is corrupt, stop and use the
   request-filtered microscope. Do not add more synchronized repetitions.
6. Ignore throughput for optimization decisions; synchronization deliberately
   changes the timing path.

Parent recurrence result:
[`2026-08-20-detpad-tp2-full25-recurrence-result.md`](2026-08-20-detpad-tp2-full25-recurrence-result.md)

Result:
[`2026-08-20-detpad-tp2-postforward-sync-result.md`](2026-08-20-detpad-tp2-postforward-sync-result.md)
