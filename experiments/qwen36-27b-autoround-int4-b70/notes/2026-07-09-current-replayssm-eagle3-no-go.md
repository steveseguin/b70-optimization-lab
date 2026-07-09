# 2026-07-09 - Current ReplaySSM EAGLE3 acceptance no-go

Status: **closed** for both local Ex0bit Qwen3.6 27B EAGLE3 checkpoints.

## Question

Earlier EAGLE3 tests predated the final ReplaySSM target-state corrections and
therefore did not conclusively answer whether the released EAGLE3 draft could
beat the current intrinsic MTP3 acceptance. The current checkpoints were
retested with corrected target auxiliary captures `(1, 31, 60)`, current
ReplaySSM state handling, target INT8 LM-head, and the webhie AutoRound INT4
target.

This was an acceptance gate, not a promotable throughput benchmark. Each row
used one cold prompt with `cached_tokens=0`, graph disabled, no async
scheduling, `k=3`, and 128 generated tokens. The low throughput includes
diagnostic/graph-off overhead and must not be submitted or advertised.

## Results

| Draft checkpoint | Verifier steps | Mean accepted drafts | Visible tokens/step | Acceptance histogram `0,1,2,3` | Diagnostic tok/s |
|---|---:|---:|---:|---|---:|
| Ex0bit compressed | 63 | `1.047619` | `2.047619` | `30,12,9,12` | `1.5114` |
| Ex0bit full | 66 | `0.969697` | `1.969697` | `30,16,12,8` | `1.3568` |

Current intrinsic MTP3 produces about `2.746954` visible target-verified
tokens/step on the fixed realistic suite. Both EAGLE3 checkpoints are therefore
materially below the current draft before their much larger proposal cost is
considered.

Evidence:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle3-current-replayssm-compressed-k3-acceptance-oneprompt-20260709T221851Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle3-current-replayssm-full-k3-acceptance-oneprompt-20260709T221908Z.json
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-current-replayssm-compressed-k3-oneprompt-20260709-verify.jsonl
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-current-replayssm-full-k3-oneprompt-20260709-verify.jsonl
```

## Decision

Do not run a full-suite or graph-on sweep for these checkpoints. They fail the
predeclared acceptance gate even after the current ReplaySSM corrections. A
future EAGLE/PRISM checkpoint may reopen the lane only if a cold acceptance
probe first exceeds intrinsic MTP3 with meaningful margin; model-card
throughput from a different target/runtime is not enough.

Together with the corrected DFlash result (`2.731579` visible tokens/step at
`52.03 tok/s`), this closes the existing external-draft shortcuts. The next
acceptance mechanism must train distinct position-specific predictors or use a
new target-matched draft, rather than optimize these released checkpoints.
