# Embedded publisher-MTP realistic suite: matched-control PASS

Date: 2026-08-10

## Decision

The integrated publisher-MTP identity clears its scoped one-B70 short
realistic-suite gate under the `matched_fresh_control_v1` quality reference.
The supplemental classification is `PASS_REALISTIC_MTP_WIN`: all 12 candidate
full token arrays and decoded contents exactly equal the matched fresh control,
and every prompt has a large D99 gain.

This does not rewrite either failed run. The first attempt remains a safely
closed parser failure. The complete measured source packet remains immutably
`FAIL` because its then-current gate compared the 32K/512 run against an
identity-mismatched legacy 4K/128 prefix oracle. The matched-control PASS lives
in a separate sealed offline supplement and binds the unchanged source
captures by SHA-256.

This is now an approved LocalMaxxing record, but not a production result. Eleven
prompts reached 512 generated tokens, while `customer-email` stopped normally
at EOS after 248. The earlier conclusion that `all_rows_full_512=false` made
the run ineligible was overstrict: all 12 rows contain the required
generated-token 1/100 timing endpoints for D99, and LocalMaxxing policy does
not require padding an ordinary EOS response to the request cap. The derived
submission packet passes local and authenticated no-write preflight. The final
POST returned `HTTP 201`, record `cmsn6b0bm0074o001uw5f9kod`, status
`APPROVED`. Middle/near-32K prompt retention, concurrency, second-card reproduction,
and sustained service validation remain open.

## Fixed identity

- model: integrated `unsloth/Qwen3.6-27B-MTP-GGUF`
- revision: `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`
- file: `Qwen3.6-27B-Q8_0.gguf`
- size: `29,047,084,160` bytes
- SHA-256: `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`
- llama.cpp commit: `15586e2d7165570fb3aa7c26e0d442e289ef69de`
- `llama-server` SHA-256:
  `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`
- VDR2 runtime manifest SHA-256:
  `4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49`
- fixed suite SHA-256:
  `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`
- GPU: isolated B70 GPU 0
- common service identity: `-c 32768 -np 1 -b 1024 -ub 1024`, F16 K/V,
  flash attention on, VDR2, one slot, ordinary EOS, no prompt/context/response
  reuse
- control: `--spec-type none`
- candidate: embedded MTP, `n_max=3`, `n_min=0`, `p_split=0.10`,
  `p_min=0.00`, explicit backend sampling, and no sidecar draft model

Each arm used one cold scored OpenAI text-completion request per fixed prompt,
with literal `cached_tokens=0`. Separate fresh server lifetimes captured the
full forensic token arrays and content. The four sequential lifetimes were
scored control, scored MTP3, forensic control, and forensic MTP3; each service
saw each prompt once.

## Preserved parser failure

The first attempt is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/
  embedded-mtp-vdr2-realistic-gpu0-20260810T100440.907192568Z
```

The scored-control client stopped on
`partial verbose token event identity mismatch` because the initial parser
required `id_slot=0` in partial verbose events while this runtime emits the
sentinel `id_slot=-1`. No complete performance measurement exists. The sole
started service stopped without a forced kill or survivor, closed its port, and
returned GPU 0 from `43 -> 43 MiB`.

- retained status: `FAIL`
- 48-entry artifact-manifest SHA-256:
  `3f2749a30005cac0a0a6203fddb2e8a9ed101ac13c79354d5ec88bb38767b1e9`
- manifest verification: `48/48`
- prospective fix: commit
  `612f6660d6f0b3738c1acf6156879a969a89cb3c`

The commit changes the partial-event sentinel expectation and its tests. It
does not alter or reclassify this failed run.

## Complete source packet and preserved FAIL

The next attempt completed all four measurement lifetimes:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/
  embedded-mtp-vdr2-realistic-gpu0-20260810T101337.129519194Z
```

Its original status remains `FAIL`; no completion marker is retrofitted.
The 132-entry manifest verifies. The sole evidence-gate failure was the legacy
prefix comparison: its sealed oracle has a 4,096-token context and a 128-token
maximum, while the current gate uses a 32,768-token allocation and up to 512
tokens. Six of 12 fresh control prefixes matched that old oracle. The six
mismatches were `code-review`, `customer-email`, `sql-debugging`,
`release-plan`, `bug-report-synthesis`, and `performance-hypotheses`.

- retained `run-status.txt`: `FAIL`
- `run-status.txt` SHA-256:
  `4f8e9e45f8a9e1843b81eaf3bdf52a6b778d415d23bf985774a9d34a43f69bd5`
- 132-entry artifact-manifest SHA-256:
  `8b0e18c529eabaf837bfb8fc2b2f7b5bc4f280c1952b741dc85e1fefc9425f89`
- manifest verification: `132/132`
- legacy prefix-oracle SHA-256:
  `e07298632346a62f78af9d532593c15f8622b166104ee157bf383bed25228b9d`

The mismatch is not evidence that context size caused a quality regression.
The oracle and current gate have different context/output identities, and
earlier same-card evidence points more strongly to ubatch sensitivity than
context size. Exact causality remains unresolved; do not tune against the stale
oracle or recast the 6/12 result as a context finding.

The immutable raw captures used by the supplement are:

| Artifact | SHA-256 |
|---|---|
| scored control | `16d87bf37f6654e5ac920849dc5c97288bea14d70904354780894d7b9fc7a29c` |
| forensic control | `8af30d579a30aedf3cadaa8f0728d883acc7d0da188bd2b30125b472f37a2ad2` |
| scored MTP3 | `0ce2399561568c4d80d112f42457fc31acedbddac576f1900e64ba88ee1352e7` |
| forensic MTP3 | `886107c29af70fba5ce0919091d1122c5e0317a0811cce9169819d65076c49c0` |

Every lifetime passed its start/stop identity, residency, port-closure, and
cleanup gates. Control loaded `28,642 MiB`; MTP3 loaded `29,911 MiB`. All four
returned GPU 0 from `43 -> 43 MiB` without a forced kill or survivor.

## Sealed supplemental PASS

The original packet was not edited. A separate offline supplement re-ran the
gates with the quality reference declared as `matched_fresh_control_v1`:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/offline-supplemental/
  embedded-mtp-realistic-stale-oracle-final-20260810T101337.KjteSJ
```

- classification: `PASS_REALISTIC_MTP_WIN`
- evidence: `evidence_passed=true`
- performance: `performance_passed=true`
- policy: `realistic_policy_passed=true`
- retained historical supplement field:
  `localmaxxing_submission_ready=false` (overstrict all-512 derivation)
- six-entry artifact-manifest SHA-256:
  `d44cef315a2d88652bdaeb9694a718897f2d301f916a4d9d419f41190519a2c3`
- completion SHA-256:
  `3eaf8d2c72bc64e2440e42486ca69b3605d357cc6e782aae79fd21c059e03c7f`
- supplemental-identity SHA-256:
  `d966b5d2996cee86faba0ef95b68afdabfcd95fb25d97078319680b8b922ae49`
- comparison SHA-256:
  `41d754812311ad657f7f59b7f51794e7b394a82096587123280fdf76dc510ae3`
- manifest verification: `6/6`

The supplement binds the scored and forensic input hashes above, verifies
fresh distinct lifetimes, one scored request per prompt, zero replay requests,
ordinary EOS, literal cache-zero usage, server/runtime/model identity, and the
sealed metrics-counter recomputation. Candidate and control full token IDs and
decoded content are exact for all 12 prompts.

## LocalMaxxing policy correction and staged packet

The conventional primary metric needs generated-token events 1 through 100,
which form 99 inter-token intervals. Every observed row reaches that window;
the shortest row reaches 248. Ordinary EOS after the primary window is valid,
and there is no all-512 rule. Suppressing EOS, padding, or retrying the prompt
would make the measurement less representative.

A focused offline builder re-verifies the 132-entry failed source manifest,
the six-entry supplemental manifest, all four scored/forensic capture hashes,
the matched-control exactness join, model/runtime/suite identity, cache-zero
policy, MTP counters, and the `11x512 + 1x248` output distribution. Its policy
tests prove that 248 is eligible, 99 fails closed, and reaching 512 on every row
is not required. The production submission helper received a narrow typed
projection fix so `gpuLayers=-1` and `mtpEnabled=true` survive into the API
request; its eligibility gates were not weakened.

- queue:
  `experiments/qwen36-27b-q8-gguf-b70/localmaxxing/qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.queue.json`
- queue SHA-256:
  `c3f6032b47dcb420041f3eff25c8c79e5d8aa1197c948f65a82e4b954fc27f23`
- exact projected API request SHA-256:
  `a2bcfd8479be27d603c967db5c2cf8785c462542cb46171d94111266b371a8ee`
- builder audit SHA-256:
  `45623b9502c7cff233ccbe0743c03aa551d529aad6917fb77daa71c543afc9b3`
- six-entry packet-artifact checksum manifest SHA-256:
  `b94c99ece2637d105179c6e178384d7b5aca364ddd5e7a2cab63cd6517fb33e6`
- local preflight: PASS
- authenticated `POST /api/speed-tests/dry-run`: `HTTP 200`, `valid=true`
- pre-submission matching-record query: no approved one-B70 `Q8_0` row for the exact
  `unsloth/Qwen3.6-27B-MTP-GGUF` category; the one returned B70 row is
  `UD-Q4_K_XL` and is identity-incompatible
- final LocalMaxxing POST: `HTTP 201`, `APPROVED`
- record: `cmsn6b0bm0074o001uw5f9kod`
- submission receipt SHA-256:
  `c4bf4970acd2f020b3a22e9fe959fcf46ab6716faaada1aab940b6e03274cbbc`
- two-entry submission-artifact manifest SHA-256:
  `a364aba10b30aee3ef70e32736adea3df3eb110c47e0ebb3dfeb8f49e5ea6090`

The payload pins the integrated publisher identity exactly:
`hfId=unsloth/Qwen3.6-27B-MTP-GGUF`, revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, and `quantization=Q8_0`.
Its primary score is `36.04870684253697 tok/s`; `tokSTotal` is the API-defined
median `(prompt_tokens + completion_tokens) / elapsed_s`,
`37.48397529291239 tok/s`. Top-level output tokens are the integer suite median,
512, while the full per-prompt distribution remains in typed local audit
metadata.

## Performance

The primary metric is the median conventional rate over the 99 inter-token
intervals between generated-token events 1 and 100 after TTFT.

| View | Control | MTP3 | MTP3/control |
|---|---:|---:|---:|
| primary D99 | `17.107772` | `36.048707` | `2.107154x` |
| matched full interval | `17.017022` | `34.545186` | `2.030037x` |
| native generated-token rate | `17.050342` | `34.612807` | `2.030036x` |
| median TTFT | `0.763991 s` | `0.785477 s` | `1.028123x` |

The minimum per-prompt D99 candidate/control ratio is `1.757122x`. The matched
full/native ratio disagreement is `0.00000114`, so the independent full-window
views agree. All preregistered speed, per-prompt, TTFT, acceptance, exactness,
and identity checks pass.

MTP3 counters across the 12 scored requests are:

- accepted tokens: `3,709`
- draft tokens: `6,448`
- draft/verifier cycles: `2,152`
- accepted/drafted: `0.575217`
- accepted per verification: `1.723513`
- effective emitted tokens per target verification: `2.723513`
- accepted positions 0/1/2: `1,722 / 1,190 / 797`

This acceptance is materially below the two-prompt diagnostic's `0.934465`,
but the target-verified realistic result still doubles both matched full and
native throughput.

## Scope and next gate

Bank this as a scoped one-B70 short realistic-suite win for the integrated MTP
identity. Keep it separate from the target-only Q8_0 baseline and from the
original packet's immutable `FAIL`. LocalMaxxing approved it as
`cmsn6b0bm0074o001uw5f9kod` under the corrected natural-EOS policy after its
authenticated server dry-run passed. Do not describe every row as full-512:
one ordinary response ended at 248. Public record readback matches the staged
identity and metrics.

The next bounded work is middle and near-32K retention, followed by the
relevant concurrency generalization and a second-card confirmation. The large
short gain is already decisive; do not spend another unchanged rerun or tune
against the stale legacy oracle.
