# 2026-08-17 Qwen3.6 27B INT4 batch-invariant RMSNorm closeout

## Decision

The approved post-reboot 25-prompt gate is complete. The batch-invariant
Gemma RMSNorm approach is **inconclusive and not production-ready**.

The fast four-prompt screen was real: 4/4 complete outputs matched the two
then-sealed controls at `106.663` conventional tok/s. It was only 3/4 against
the later matched-current-source 25-target subset because long-rollover changed
at token 391 across target starts. The matched-source 25-prompt result did not
generalize. It matched only 12/25 complete target outputs and measured
`93.445681` tok/s under the conventional 99-interval metric. It therefore
failed both required gates: exact target parity and at least `100 tok/s`.

The run passed smoke, cache-zero, realistic-suite, and objective-quality
checks. Those checks do not override the token-parity or performance failures.
No LocalMaxxing submission was made. No additional diagnostic was launched,
and the installed runtime was left unchanged as requested.

## Final matched gate

| Field | Target | Speculative candidate |
| --- | --- | --- |
| Source identity | lab `f0e86b89`, vLLM `a63ff886`, kernels `6a40e2ba`; cumulative patch SHAs `0f0e1e1d`, `e8f154cb`, `10d7cb28` | exactly the same |
| Runtime | TP2 target-only, PIECEWISE M1 | TP2 MTP3, PIECEWISE M4 with exact GDN eager break |
| RMSNorm | fixed per-row batch-invariant Triton reduction | same |
| Warmup | real 14-token smoke | real 14-token smoke |
| Cache | 25/25 zero | 25/25 zero |
| Objective quality | pass | pass |
| Full token parity | reference | **12/25 exact** |
| Conventional median | `47.448061 tok/s` | **`93.445681 tok/s`** |
| Legacy-inclusive median | `47.927334 tok/s` | `94.389577 tok/s` |

Target root:
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-25-target-a-20260817T063000Z`
(manifest SHA256 `277b0bcc72fa9c00ed63a0d051bc3e313a43c86ab0637f770410c2ad3748f703`).

Candidate root:
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-25-spec-b-postreboot-20260817T124553Z`
(manifest SHA256 `56c066b7b00315bab4a1870b7d3b9f5b01268c2ab7b09fce8d0f6747cce339e6`).

The candidate mismatch set is prompt indices
`0,1,5,6,8,10,11,12,14,15,19,21,24`. The structured-extraction row also
changed its natural completion length (`435` candidate tokens versus `418`
target tokens). The compact machine-readable record contains each first-diff
position and token pair.

## Relevant controls

Rates marked diagnostic include raw execution, tracing, or a one-prompt
canary; they are not comparable to the warmed normal gate.

| Control | Correctness | Execution | Warmup | Conventional throughput |
| --- | --- | --- | --- | ---: |
| Current matched target 25 | reference; quality/cache pass | compiled PIECEWISE target M1 | yes | `47.448` |
| Safe-default candidate 25 | 17/25 exact | compiled PIECEWISE MTP3; exact GDN eager break | yes | `96.519` |
| Input-dependency four-prompt | 4/4 vs then-sealed controls; 3/4 vs later same-source target subset | compiled PIECEWISE MTP3 | yes | `110.675` |
| Input-dependency matched 25 | 15/25 exact | compiled PIECEWISE MTP3 | yes | `96.386` |
| Stateless M4/M1 operator oracle | 8/8 operator cases bit-exact | direct W4A16, FP16 BA, and W8A8 calls | no | n/a |
| Live W4A16 oracle | 11,008 comparisons/rank exact; endpoint still wrong | raw verifier with live shadow calls | no | `4.836` diagnostic |
| Live GDN-state oracle | 8,256 comparisons/rank exact; endpoint still wrong | raw verifier with live state shadow | no | `3.120` diagnostic |
| Progressive one-row FA | endpoint unchanged and wrong | raw verifier, progressive FA | no | `6.334` diagnostic |
| Serial Gemma RMSNorm | 128/128 target-exact | raw verifier, four M1 RMS calls | no | `5.847` diagnostic |
| Fast batch-invariant RMSNorm | 128/128 target-exact | raw verifier, one fixed-geometry M4 Triton call | no | `5.642` diagnostic |
| Fast RMSNorm four-prompt | 4/4 vs then-sealed controls; 3/4 vs later current-source target subset | compiled PIECEWISE MTP3; exact GDN eager break | yes | `106.663` |
| Fast RMSNorm target 25 | reference; quality/cache pass | compiled PIECEWISE target M1 | yes | `47.448` |
| Fast RMSNorm pre-reboot candidate | no inference result; host soft-lock during load | startup only | no | n/a |
| Fast RMSNorm post-reboot candidate | **12/25 exact**; quality/cache pass | compiled PIECEWISE MTP3; exact GDN eager break | yes | **`93.446`** |

The earlier dependency controls, including fixed-M4, synthetic-zero,
raw/compiled dependency scopes, and the all-INT4 correction, remain in the
[dependency closeout](2026-08-17-qwen36-int4-input-dependency-closeout.md).

## What was established

- The focused output-77 mismatch was an accepted verifier row with only a
  `0.015625` packed top1/top2 score margin.
- Stateless and live W4A16, W8A8, FP16 BA, and GDN shadow comparisons did not
  explain that focused mismatch.
- Serial one-row Gemma RMSNorm and a fixed per-row reduction geometry both
  restored the focused target path. This is strong causal evidence that the
  old M4 RMS reduction could cross close argmax boundaries.
- Fixing that boundary was insufficient for general target equivalence: the
  full suite still differed on 13 prompts.

## Contradictions and confounders

1. Both the dependency and RMSNorm approaches passed small warmed suites above
   `100 tok/s`, then failed the matched 25-prompt gate. Small canaries were not
   representative of whole-suite correctness or throughput.
   All three historical four-prompt candidates share the same four output
   hashes, while the later current-source target changes long-rollover at token
   391. The phrase “4/4 exact” is therefore control-specific, not universal.
2. The RMSNorm change is causally useful on the focused near-tie, but 13 later
   mismatches remain. It is therefore a partial arithmetic correction, not a
   complete speculative-equivalence fix.
3. The post-reboot 25-prompt candidate is materially slower than its own
   four-prompt screen (`93.446` versus `106.663`). Prompt mix and acceptance
   distribution are live performance confounders; the normal suite is the
   governing metric.
4. The current-source target has only one complete 25-prompt start. Historical
   target streams have shown close-boundary variability, so the 12/25 figure
   is not a universal proof of which side is mathematically canonical.
   Performance still fails independently, so this caveat cannot rescue the
   candidate.
5. The candidate requested native GDN capture, but exact recurrent mode
   deliberately suppresses it. The honest identity is PIECEWISE model
   execution with an eager/dynamic exact-GDN graph break.
6. INT4 and INT8 completion barriers and the larger exact-GDN source stack were
   simultaneously active. The focused RMSNorm patch cannot be presented as a
   standalone production result without rebuilding and requalifying a cleaned
   source identity.
7. The pre-reboot candidate failure was a host-kernel soft lock during model
   loading, not a model correctness or speed result. It is retained only as an
   operational negative.

## Preserved artifacts

- [Structured closeout](../data/qwen36-27b-autoround-int4-batch-invariant-rmsnorm-closeout-20260817.json)
- [Exact tested source/config packet](../patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/README.md)
- [Sealed raw-root manifest index](../data/qwen36-27b-autoround-int4-batch-invariant-rmsnorm-sealed-roots-20260817.sha256),
  SHA256 `bde0a3ae1fcd5af672f2ecb95af1a23dba01536f0a6039a842ca7ca77f70dd50`
- Packet manifest SHA256:
  `99ce6777a28f08f25492a722ce45e28f2349ec3994a19926189b2a1ed32e3e21`
- Final failed-gate manifest SHA256:
  `56c066b7b00315bab4a1870b7d3b9f5b01268c2ab7b09fce8d0f6747cce339e6`

The patch packet intentionally labels the focused fast RMSNorm delta
experimental. There is no production-ready patch from this approach because
the normal parity and performance gates failed.
