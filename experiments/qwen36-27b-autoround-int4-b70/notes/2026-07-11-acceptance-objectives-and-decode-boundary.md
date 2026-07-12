# MTP3 acceptance objectives and decode-boundary correction

## Classification

Diagnostic offline training and evaluator correction. No endpoint throughput
run, quality promotion, record, or LocalMaxxing submission.

## Objective work

The intrinsic-MTP trainer gained default-off objectives intended to align
training with target-verified accepted prefix:

- a soft prefix-survival surrogate;
- a greedy target-top1 multiclass margin;
- optional teacher KL reconstructed from stored target hidden states;
- per-start, per-sample, family, and cluster acceptance summaries.

All weights default to zero and preserve the prior CE path. Teacher KL was not
used because its checkpoint BF16 LM head is not the endpoint's runtime INT8
BF16-scale teacher. The soft-survival term is explicitly a softmax-sampling
surrogate, not the expectation of the temperature-zero greedy endpoint.

The reproducible four-GPU launcher is:

`../scripts/run-acceptance-objective-mtp3-training-4gpu.sh`

It supports `MATRIX=mixed`, `margin`, and `conditional`, trains on the disjoint
v6 chat trajectory corpus, and keeps all results diagnostic-only.

## Validity audit and correction

Independent review found that the old fixed-corpus evaluator started at every
sequence position. Of 2,338 starts, 850 were prompt/prefill positions and only
1,488 were decode positions. Those old acceptance values therefore do not
measure endpoint draft behavior cleanly and must not be used as an endpoint
gate.

`--decode-only-starts` now begins at `num_prompt_tokens - 1`, whose first
target is the first generated token. It reports excluded prompt starts and
fails closed for samples without prompt length. The launcher also recomputes a
matched shared-checkpoint control instead of using a stale hard-coded value,
and records all model and corpus paths.

The training and realistic corpora had no matching prompt IDs, complete token
streams, or 64-token prefixes across 1,151 training trajectories and 12
realistic trajectories. However, the same 12-prompt corpus has been reused for
candidate selection, so it is now labeled a **reused realistic selection
suite**, not an untouched final promotion gate. A future candidate must be
selected on disjoint heldout/cross-validation data and confirmed by the strict
fresh endpoint and quality gates without adapting to those outcomes.

## Corrected decode-only results

Compact tracked result:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-acceptance-objectives-decode-only-20260711.json`

All rows use 1,488 decode starts and exclude the same 850 prompt starts:

| candidate | accepted drafts/start | delta vs shared |
| --- | ---: | ---: |
| shared checkpoint | `1.338710` | `0` |
| prior all-step CE, lr `2e-5` | `1.512097` | `+0.173387` |
| all-step margin `0.03` | **`1.516801`** | **`+0.178091`** |
| all-step margin `0.1` | `1.510081` | `+0.171371` |
| all-step margin `0.3` | `1.508737` | `+0.170027` |
| all-step margin `1.0` | `1.500000` | `+0.161290` |
| conditional CE, lr `1e-5` | `1.487903` | `+0.149194` |
| conditional CE, lr `2e-5` | `1.511425` | `+0.172715` |
| conditional + margin, lr `1e-5` | `1.491935` | `+0.153226` |
| conditional + margin, lr `2e-5` | `1.509409` | `+0.170699` |

The best margin result adds only seven accepted drafts over the prior CE
checkpoint across 1,488 starts (`+0.004704` per start), too small to attribute
or promote. Every candidate remains below the predeclared estimated endpoint
requirement of `+0.205609` accepted drafts/start.

## Decision

Close loss-only position-FC adaptation without an endpoint run. Do not tune
more objective weights against the reused 12-prompt selection set. Retain the
trainer objectives and corrected evaluator for future, larger, genuinely
disjoint MTP adaptation work. The immediate performance work returns to
reducing the target verifier's roughly `25 ms` per MTP step; reaching 100 tok/s
still needs about `2.1 ms/step` at current acceptance.
