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

The corrected four-GPU matrix trains block width `k=4`, the fastest historical
DFlash endpoint shape (`54.84 tok/s`, versus a much more expensive verifier at
`k=8`). It compares stronger layer-only rates, hard prefix survival, and a soft
expected-prefix objective. Active artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-k4-mixed-highlr-4gpu-20260710T113610Z
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
