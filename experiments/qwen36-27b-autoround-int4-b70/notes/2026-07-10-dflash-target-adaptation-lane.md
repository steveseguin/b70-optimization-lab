# Target-matched DFlash adaptation lane (2026-07-10)

## Status

The corrected corpus, first 200-step screen, and 2,000-step follow-up are
complete. Both historical screens are now classified as exploratory negatives
because an audit found an offline attention-semantics mismatch and overly fine
statistical clustering. A corrected endpoint-matched `k=4` screen is in
progress. This is draft research, not endpoint throughput, not a quality claim,
and not LocalMaxxing eligible.

## Why reopen DFlash

The corrected public Qwen3.6-27B DFlash checkpoint is mechanically functional,
but on the fixed realistic chat suite it produced only `1.731579` accepted
drafts (`2.731579` visible tokens/step) and `52.03 tok/s`. That correctly closed
blind Intel kernel porting around the public checkpoint. It does not close a
target-matched adaptation: the public draft was trained against the original
BF16 target while this lane verifies against the Webhie AutoRound INT4 target
and runtime INT8 LM head.

Upstream DFlash still states that its training recipe will be released later,
so this project implements a bounded local offline adaptation from the paper's
published contract:

- random response anchors;
- one clean target-owned token followed by masked block positions;
- parallel block prediction with target hidden features injected as KV;
- frozen target embedding and LM head;
- exponentially decayed token loss, with `gamma=4` for block size 8;
- exact longest-prefix acceptance as the pre-gate metric.

Primary references:

- <https://github.com/z-lab/dflash>
- <https://arxiv.org/abs/2602.06036>

## Corrected conditioning corpus

The earlier five-aux corpus used layers `1,16,31,46,61`. The corrected vLLM
DFlash extraction uses effective hidden-state indices `2,17,32,47,62`; using
the old corpus would adapt the wrong interface. A fresh four-GPU collection was
completed against the separate v6b context suite:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/
qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z
```

It contains `384` prompts and `61,349` usable rows across `12` realistic
families, with no continuity breaks and no bad auxiliary-state files. Shards
`0..2` are training data; shard `3` is held out. A compact collection summary
is preserved under `diagnostics/` beside this note's experiment lane.

The fixed realistic final suite is not part of training. Endpoint candidates
must still run each final prompt once, cold, with `cached_tokens=0`.

## Implementation

`scripts/train-qwen27-dflash-offline.py` reconstructs the actual DFlash block
from target-owned sequence traces and records per-anchor accepted-prefix rows
for paired prompt/family analysis. It supports:

- evaluation only;
- FC / FC+norm adaptation;
- transformer-layer adaptation matching the paper's scope;
- full-draft adaptation for bounded comparison;
- uniform, paper-style position-decay, and accept-until-fail loss support;
- differentiable expected-prefix loss with a first-token CE floor;
- endpoint-matched mixed attention or historical public non-causal attention;
- safetensors export of only the trained draft parameters.

`scripts/merge-qwen27-dflash-adapter.py` provides the default-off endpoint
bridge. It validates adapter keys, shapes, and dtypes; writes one merged
checkpoint instead of relying on duplicate safetensor glob order; and records
base, adapter, and output SHA-256 identities. A derived draft is still only an
experiment artifact until the declared target verifies it through the strict
fresh endpoint and quality gates.

The first four-GPU smoke matrix is reproducible through
`scripts/run-dflash-adaptation-smoke-4gpu.sh` in this experiment folder. It
compares FC, transformer-layer, full-draft paper-decay, and full-draft
accept-until-fail variants on the same heldout anchors.

The evaluator now uses the exact endpoint-style INT8 target LM head with BF16
per-output-channel scales. During adaptation it retains that INT8 forward and
token choice while using the frozen BF16 head only as a straight-through
gradient. Baseline and final evaluations use three passes and the per-anchor
median because exact XPU reruns can move a small number of near-tied argmax
rows. The corrected evaluator also records technical repeat disagreement rather
than treating medians as error-free observations.

## First 200-step screen

The first four-GPU matrix found only small, statistically unsupported changes:

| Candidate | Baseline visible | Final visible | Delta | Prompt-cluster 95% CI | Holm p | Result |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| FC, paper decay, `3e-6` | 3.1094 | 3.1152 | +0.0059 | `[-0.0364, 0.0485]` | 0.715 | no win |
| layers, paper decay, `1e-6` | 3.1016 | 3.1230 | +0.0215 | `[-0.0120, 0.0545]` | 0.633 | no win |
| all draft, paper decay, `1e-6` | 3.1074 | 3.1152 | +0.0078 | `[-0.0275, 0.0475]` | 0.715 | no win |
| all draft, accept-until-fail, `1e-6` | 3.0938 | 3.1152 | +0.0215 | `[-0.0196, 0.0546]` | 0.633 | no win |

This result is why the old fixed `3.3` threshold is not used as a statistical
claim. Small effects are still recorded, but advancement also requires enough
candidate-specific throughput value to matter. The full historical analysis is
preserved as
`diagnostics/qwen27-dflash-adaptation-smoke-paired-20260710.json`; the large
adapter files and raw per-anchor summaries remain on the USB artifact volume.

## 2,000-step follow-up

The follow-up used four GPUs, `1,024` heldout anchors, and three evaluation
passes. It tested transformer layers at `3e-6` and `1e-5`,
accept-until-fail layers at `1e-5`, and all-draft accept-until-fail at `1e-5`:

| Candidate | Baseline visible | Final visible | Delta | Effective `k=4` delta | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| layers, paper decay, `3e-6` | 3.1064 | 3.1025 | -0.0039 | -0.0078 | loss |
| layers, paper decay, `1e-5` | 3.1006 | 3.1182 | +0.0176 | +0.0107 | too small |
| layers, accept-until-fail, `1e-5` | 3.1074 | 3.1279 | +0.0205 | +0.0117 | weak positive, too small |
| all draft, accept-until-fail, `1e-5` | 3.1084 | 3.1143 | +0.0059 | +0.0068 | too small |

The best full-prefix row had an exploratory prompt-cluster interval above zero
before multiplicity correction, but missed the four-way Holm threshold
(`p=0.0694`) and improved effective `k=4` depth by only `0.0117` token/step.
That is about `0.4%` of the offline `k=4` depth and cannot justify an endpoint
run. Its artifact root is:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-long-4gpu-20260710T041218Z
```

## Audit correction before the next matrix

Two independent reviews found that the earlier evidence was weaker than its
initial labels implied:

1. The public Transformers DFlash forward used no explicit attention mask, so
   all five layers were evaluated as non-causal. The repaired vLLM endpoint uses
   causal sliding-window attention for the first four draft layers and
   non-causal attention for the final full-attention layer. The trainer now has
   explicit `endpoint-mixed` and `public-noncausal` modes; endpoint-mixed is the
   default. On the same 64 heldout `k=4` anchors, the untouched checkpoint gave
   `2.84375` visible tokens/step with endpoint-mixed versus `2.828125` with the
   historical public mode. The mismatch was small on that sample but real.
2. The heldout shard has only three families, crossed with eight tasks and four
   closely related variants. Treating all 96 prompts as independent overstates
   evidence. New records preserve `task`, `variant`, and `scenario`; exploratory
   inference clusters at 24 `family x task` scenarios, reports technical repeat
   disagreement, rejects train/heldout prompt overlap, and requires a frozen
   confirmation on untouched data or endpoint traces before promotion.

The corrected four-GPU matrix trained block width `k=4`, the fastest historical
DFlash endpoint shape (`54.84 tok/s`, versus a much more expensive verifier at
`k=8`). It compared stronger layer-only rates, hard prefix survival, and a soft
expected-prefix objective. Artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-k4-mixed-highlr-4gpu-20260710T113610Z
```

Results:

| Candidate | Baseline visible | Final visible | Scenario delta | Scenario 95% CI | Stability | Decision |
| --- | ---: | ---: | ---: | --- | --- | --- |
| layers, paper decay, `3e-5` | 2.7813 | 2.7871 | +0.0060 | `[-0.0033, 0.0157]` | fail | no win |
| layers, hard survival, `3e-5` | 2.7773 | 2.7949 | +0.0188 | `[0.0053, 0.0326]` | fail | weak positive, too small |
| layers, soft prefix, `1e-5` | 2.7803 | 2.7861 | +0.0074 | `[-0.0068, 0.0214]` | fail | no win |
| layers, soft prefix, `3e-5` | 2.7813 | 2.7881 | +0.0077 | `[-0.0059, 0.0210]` | fail | no win |

Hard survival passed the exploratory scenario/Holm zero-effect test
(`p=0.0305`) but not the predeclared `+0.25` minimum useful effect. Its final
per-anchor repeat disagreement was also `1.66%`, above the `1%` technical
stability limit. A `+0.0188` token/step lift cannot move the historical
`54.84 tok/s` DFlash endpoint past the valid `68.236 tok/s` record, much less
to `100 tok/s`, so no adapter was merged and no endpoint run was spent. Compact
analysis is preserved as
`diagnostics/qwen27-dflash-k4-mixed-highlr-paired-20260710.json`.

The next mechanism is zero-initialized block-position conditioning inside the
DFlash queries/layers. Prior intrinsic-MTP work showed a transferable
`+0.3939` visible-token gain from position-specific input projections, whereas
adding capacity only at the final output seam plateaued. Position conditioning
tests that architectural signal in DFlash without changing the target model;
the target still verifies every emitted token.

The implementation adds either one FP32 input-position bias (`25,600`
parameters at `k=4`) or one FP32 per-layer position bias (`128,000`
parameters), cast to the draft activation dtype at use. Both are initialized to
zero. A 64-anchor three-way identity check matched every accepted prefix for
control, input bias, and layer bias (`2.84375` visible tokens/step in all three
cases). A one-step layer-bias smoke changed only
`xpu_layer_position_bias`, proving the intended parameter boundary.

The first four-GPU matrix compared input bias at `1e-3` and layer bias at
`3e-4`, `1e-3`, and `3e-3` for 4,000 steps. Artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-position-k4-mixed-4gpu-20260710T114740Z
```

| Candidate | Baseline visible | Final visible | Scenario delta | Scenario 95% CI | Decision |
| --- | ---: | ---: | ---: | --- | --- |
| input bias `1e-3` | 2.7842 | 2.7783 | -0.0023 | `[-0.0442, 0.0398]` | no win |
| layer bias `1e-3` | 2.7803 | 2.8037 | +0.0264 | `[-0.0141, 0.0639]` | inconclusive |
| layer bias `3e-3` | 2.7822 | 2.5479 | -0.2296 | `[-0.2737, -0.1849]` | loss |
| layer bias `3e-4` | 2.7764 | **2.8418** | **+0.0664** | **`[0.0281, 0.1049]`** | real exploratory gain, continue |

The `3e-4` layer-bias curve rose monotonically at each checkpoint
(`2.7891`, `2.7979`, `2.8242`, `2.8418`) and passed the exploratory
scenario/Holm zero-effect test (`p=0.0060`). It is the first clear
target-matched DFlash adaptation gain. It still misses the `+0.25` minimum
useful effect and has `1.37%` final repeat disagreement, so it is not an
endpoint or LocalMaxxing candidate yet. Compact analysis is preserved as
`diagnostics/qwen27-dflash-position-k4-paired-20260710.json`.

The exact `3e-4` adapter is now being continued for 8,192 steps at constant
rates `5e-5`, `1e-4`, `2e-4`, and `3e-4` on four GPUs. This is justified by the
monotonic curve and tests convergence/overshoot without changing architecture.
Active artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-position-cont-k4-mixed-4gpu-20260710T115404Z
```

## Advancement rule

Do not use a fixed scalar acceptance cutoff as proof. Retain paired per-anchor
rows, cluster exploratory analysis by scenario, and keep family results
descriptive until there are more than three independent heldout families. A
candidate advances only if its conservative effect improves accepted depth,
exceeds technical repeat instability, and its candidate-specific target+draft
step-cost projection has material headroom toward `100 tok/s`.
Offline acceptance is never a throughput or target-quality claim. A promoted
candidate still needs the strict fresh endpoint suite, card/order crossover,
repeat64 baseline-quality match, exact identity capture, and a new record above
`68.236263 tok/s` before LocalMaxxing submission.
