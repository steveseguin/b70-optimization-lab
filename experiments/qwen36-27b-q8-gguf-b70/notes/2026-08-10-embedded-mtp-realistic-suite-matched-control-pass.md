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

This is not a LocalMaxxing submission or a production result. Eleven prompts
reached 512 generated tokens, while `customer-email` stopped normally at EOS
after 248; consequently `all_rows_full_512=false` and
`localmaxxing_submission_ready=false`. Middle/near-32K prompt retention,
concurrency, second-card reproduction, and sustained service validation remain
open.

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
- submission: `localmaxxing_submission_ready=false`
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
original packet's immutable `FAIL`. Do not publish it as a full-512
LocalMaxxing record: the natural 248-token `customer-email` row makes the
current packet ineligible, and no submission was made.

The next bounded work is middle and near-32K retention, followed by the
relevant concurrency generalization and a second-card confirmation. The large
short gain is already decisive; do not spend another unchanged rerun or tune
against the stale legacy oracle.
