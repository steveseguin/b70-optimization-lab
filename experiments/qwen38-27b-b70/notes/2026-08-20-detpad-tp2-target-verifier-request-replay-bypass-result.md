# Qwen3.8 TP2 target/verifier request-selected replay-bypass result

Date: 2026-08-20

Classification: **terminal negative; target/verifier replay bypass is insufficient**

Preregistration:
[`2026-08-20-detpad-tp2-target-verifier-request-replay-bypass-prereg.md`](2026-08-20-detpad-tp2-target-verifier-request-replay-bypass-prereg.md)

Structured result:
[`2026-08-20-int4-detpad-tp2-target-verifier-request-replay-bypass-result.json`](../data/2026-08-20-int4-detpad-tp2-target-verifier-request-replay-bypass-result.json)

## Result

T1 completed with runner status 0, passed the sealed arm checker and quality
baseline, and produced a nonzero 512-token prompt-24 response. Its independently
reviewed checksum-manifest SHA authorized exactly one T2.

T2 passed every arm-local model, source, cache, engagement, freshness and
supervision gate, but exited with the preregistered scientific status 14 because
its complete token arrays matched T1 on only **24/25** prompts. The sole mismatch
was prompt 24, `holdout--long-rollover-repository-audit`: both streams were 512
tokens long and agreed through generated token 468, then split at zero-based
token 469 (`9345` in T2 versus `3669` in T1).

Both prompt-24 outputs were sane existing families rather than the 512-zero
catastrophe:

- T1 matched B2 exactly, with token-array SHA-256
  `e616edc891bb591457b5c410c63d09795b5023c7cc4b403052df2e57e2950407`
  and output SHA-256
  `c923f52f0159d5a1a8163d77ebba9b911bd9c658efc85ef83383b0a0c0a1428b`;
- T2 matched R1, R2, S1 and target A exactly, with token-array SHA-256
  `b1ad815bceff49895fedb75552c6f7d8a4650a965f818aeb4c20fb3685c8f20b`
  and output SHA-256
  `471a54e871126200a286dedbc80c6c689ce83093be06e7350b551a512cf364dd`.

The all-25 comparison sharpens that boundary:

- T1 matched target A on 17/25; T2 matched it on 18/25 because prompt 24
  joined the target-A family;
- T1 matched B2 on 23/25, differing at prompt indexes 6 and 11; T2 matched B2
  on 22/25, differing at 6, 11 and 24;
- T1 matched the combined-treatment R1/R2 pair on 24/25, differing only at
  prompt 24; T2 matched R1/R2 on 25/25; and
- T2 matched S1 on 23/25, differing at prompt indexes 6 and 11.

For a durable whole-suite binding, SHA-256 over compact JSON containing the
prompt-index-sorted nested `token_ids` arrays was
`9fc260b5a0d81fd49768ad001a1754d2249367d37114d33c7d1ba43b78101bca`
for T1 and
`c5163467db2a3c42589ead9a5c293a81c7955cce6928cc585a4ebf4750cea628`
for T2. The T2 digest is also the R1 and R2 whole-suite digest.

This is a valid recurrence result, not an infrastructure failure. The exact
same target/verifier treatment emitted two prompt-24 families in its one
preregistered pair, so request-selected target/verifier replay bypass alone is
not sufficient for full-25 repeatability.

## Identity, cache and engagement

Both arm reports recorded sealed status `passed` with no errors. They bound:

- repository HEAD `a750f01ef2d52a8d6d8c2d53ad9850f658c182cd`;
- vLLM HEAD `44fc8fde09fc311d3099dab10366b672d9142ea4` plus only
  the marker hunk, with authoritative live-diff SHA-256
  `4193f05e8f255cf07de81360eff031fdb2e468218c2660850d69c9f750369683`;
- TP2 on physical GPUs 2,3, engine seed 0, request seed 1, FP16, AutoRound
  INT4, MTP5, target INT8 head, draft INT4 head and both fallback margins 0;
- composite graph-stage manifest SHA-256
  `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`,
  native extension SHA-256
  `4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0`,
  and graph-safe FA SHA-256
  `33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739`;
- sealed b991 cache manifest SHA-256
  `f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`
  and tree SHA-256
  `723c1599060f5c9c82dc5731cc75b50620c79d202b34ee99b8390d3aec20acbe`,
  with 3,795 entries, 3,246 files and 395,855,113 bytes; and
- exactly two outer and four AOT direct loads, no compile/save negatives,
  byte-identical pre/post cache manifests, and zero cache-byte delta.

Each arm recorded selector effective/expected values 1, umbrella bypass
effective/expected values 0, and drafter graph disable 0. Each had exactly one
Worker_TP0 N=1/query-length-6 engagement marker; six exact startup-capture
records covering both mixed prefill/decode and uniform decode PIECEWISE; one
Worker_TP0 graph-capture-finished event; two INT4 pad markers across ranks 0
and 1; one `cudagraph_metrics=False` marker and zero CUDAGraph metrics rows or
output; and no umbrella, drafter-disable, lazy-capture, traceback, compile or
save negative.

Speculative decoding remained active. T1 had 28 fully parsed metrics rows with
9,174 accepted of 18,405 drafted tokens (`49.8452%`); T2 had 22 rows with
8,441 accepted of 17,475 drafted tokens (`48.3033%`). T1 passed the frozen
quality baseline; T2 skipped quality as preregistered.

## Performance is descriptive only

Preferred medians were `60.7402778418` and `61.1355733403 tok/s`; their
two-arm central value was `60.9379255910 tok/s`. Legacy-inclusive medians were
`61.3538160018` and `61.7531043841 tok/s`, central value
`61.5534601930 tok/s`.

T2 was `0.651%` faster than T1 under the preferred metric, but their central
value was **39.739% below** B2's `101.1236430227 tok/s`. This diagnostic
changes target/verifier replay selection and includes a one-time marker source
delta. Its throughput is nonpromotable and must not be submitted.

## Interpretation and decision

The result excludes one narrow explanation for the earlier combined R1/R2
positive: target/verifier request-selected replay bypass by itself did not make
the full 25-prompt lane repeatable. T2 happened to reproduce the combined
R1/R2 token family exactly, while T1 differed only at the established prompt-24
token-469 split. That observation does not prove that drafter M6-to-M1
geometry, drafter replay, or startup capture/allocation history caused the
combined pair's exactness; untreated recurrence was already present and the
remaining components were not isolated here.

The preregistered campaign is complete. Preserve both arms by the manifests
below. Run no T3, retry, relabel or performance sweep from this treatment. Any
future split of drafter graph geometry or startup history requires a separate
source audit and preregistration.

## External artifacts

| Arm | Artifact root | Checksum manifest SHA-256 | Bench SHA-256 | Sealed gate SHA-256 |
| --- | --- | --- | --- | --- |
| T1 | `/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-target-request-replay-bypass-t1-20260820` | `c4cc9c614d563ce2a253c49ab17cbdc9aa8ae8a482227bc396d825c631d0d6e7` | `f73ff8148c2152901a362b6db6491e2cee3003246cf69ebe7c4b0c57e643be59` | `472d8c0354fd11eeadcde2e37a8a58703336c7f5916d31590d675b2ea1ae041a` |
| T2 | `/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-target-request-replay-bypass-t2-20260820` | `8b24cd49b1faa4711fe3f31621d863a538d9f1dd88f2e47e42b32c2dc0c28a1d` | `5aaf250b62f1f5ad3f263a2f39984eb01ad3c22a6f8dfacbce48045f14ffa6d3` | `7c1e777869780eed509d2eb6fc8ef6e17999af36328c04570fb1af93c0ae1f8f` |

T1 quality result SHA-256:
`04fdacebe530a6c67b88dc0ff7f0ffd8f77460987ccecbf4cf38f1d2bda3ef4d`.
T2 token-parity report SHA-256:
`4063894c1107ce8b91bae5b783b208b18f53a6e7eb754f1759337c6161c655f6`.
Both enclosing checksum manifests were independently reverified before this
packet was written.
