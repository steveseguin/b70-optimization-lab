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

The exact `3e-4` adapter was continued for 8,192 steps at constant rates
`5e-5`, `1e-4`, `2e-4`, and `3e-4` on four GPUs. This tested
convergence/overshoot without changing architecture. Artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-position-cont-k4-mixed-4gpu-20260710T115404Z
```

Every continuation regressed: final raw deltas were `-0.0254`, `-0.0225`,
`-0.0508`, and `-0.0469` token/step respectively. Scenario-cluster analysis
also found no positive row. Preserve the original `3e-4`/4,000-step adapter as
the additive-bias optimum; do not continue it again. Compact continuation
analysis is
`diagnostics/qwen27-dflash-position-continuation-paired-20260710.json`.

Operational caveat: the runner file was edited while the first continuation
process was still reading it. Bash reads script files incrementally, and the
changed file offsets caused that process to launch a duplicate matrix after the
first summaries were written. The duplicate process group was terminated before
it overwrote adapters/summaries, but it did overwrite the first run's stdout
logs. The summaries, adapters, and compact paired analysis remain valid; do not
use those stdout logs as first-run evidence. The runner now re-executes an
immutable `/tmp` snapshot and removes it on exit, so later source edits cannot
alter an active matrix.

The next architecture uses zero-output, per-layer and per-position low-rank
query residuals:

```text
hidden += up[layer, position](silu(down[layer, position](hidden)))
```

Ranks `32/64/128/256` add about `8.2M/16.4M/32.8M/65.5M` trainable parameters.
The up projection starts at exactly zero; a 64-anchor separate-process check
differed on one known unstable argmax row, while direct algebra and the stored
zero up tensor prove the residual itself is exactly zero. A one-step XPU smoke
updated both intended tensors. Active four-GPU artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-query-lora-k4-mixed-4gpu-20260710T120525Z
```

The full 8,192-step matrix completed cleanly. All four ranks produced a real
exploratory lift, but none was large or stable enough to justify endpoint
integration:

| Candidate | Baseline visible | Final visible | Raw delta | Scenario delta | Scenario 95% CI | Stability | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| rank 32, `3e-4` | 2.7803 | 2.8809 | +0.1006 | +0.1081 | `[0.0566, 0.1563]` | fail | positive, too small |
| rank 64, `2e-4` | 2.7803 | **2.9102** | **+0.1299** | **+0.1397** | **`[0.0819, 0.1913]`** | fail | best scenario result, too small |
| rank 128, `1.4e-4` | 2.7783 | 2.8809 | +0.1025 | +0.1135 | `[0.0600, 0.1658]` | fail | positive, too small |
| rank 256, `1e-4` | 2.7783 | 2.9082 | **+0.1299** | +0.1381 | `[0.0767, 0.1952]` | fail | tied raw best, too small |

All four pass the exploratory zero-effect test after Holm correction, but all
miss the predeclared `+0.25` useful-effect floor. Candidate repeat disagreement
was `1.17%` to `1.56%`, above the `1%` technical-stability limit. The larger
ranks did not materially outperform rank 64, so adding generic query capacity
has reached diminishing returns. Do not spend an endpoint run on these
adapters. Compact paired analysis is preserved as
`diagnostics/qwen27-dflash-query-lora-k4-paired-20260710.json`; full summaries
and adapters remain under the USB artifact root above.

## Next lane: DFlare-style target-layer fusion

The next mechanism is not another generic residual. The official Tencent
AngelSlim DFlare implementation identifies DFlash's shared target-conditioning
representation as a narrow bottleneck. It gives each draft layer its own
learned mixture over a broad set of target hidden layers and also separates
context K/V projections from noise-token K/V projections. Relevant upstream
sources are:

```text
/home/steve/src/AngelSlim/
  angelslim/compressor/speculative/train/models/draft/qwen_dflare.py
  docs/source/features/speculative_decoding/dflare.md
```

The inspected AngelSlim source identity is
`3715056a434044f45e080e4411947b9aaabdfafb`. The independent upstream
vLLM Speculators DFlash training reference was also captured locally at
`73ec09f604f962f22f40859e86a39fd5b6ec1ba3`; it confirms that on-policy target
responses and native target hidden-state extraction are the intended training
shape, but it does not yet implement DFlare's layer-wise fusion.

Our corrected corpus already contains five broad, endpoint-correct target
layers (`2,17,32,47,62`), so the first screen can isolate the layer-wise fusion
idea without collecting new traces. Preserve the public checkpoint exactly at
initialization by retaining the existing shared `fc` projection and learning
zero-initialized per-draft-layer residual mixing coefficients over the five raw
target states:

```text
base = fc(concat(aux[0:5]))
context[layer] = hidden_norm(base + sum_t delta[layer,t] * aux[t])
```

`delta=0` is algebraically identical to the current checkpoint. The first
screen adds only `draft_layers x target_layers = 25` parameters; its extra
serving work is a 25-coefficient vector mix, not another matrix projection or
draft layer. If this does not produce a material acceptance
gain, the second DFlare mechanism is a separate context/noise K/V adapter,
initialized from the existing shared K/V projections so the initial forward is
exact. Both remain offline diagnostics until a candidate passes independent
endpoint acceptance and strict fresh target-verified speed/quality gates.

Implemented as the default-off `layer-target-fusion` training scope. A direct
BF16 XPU check produced an all-zero residual and exact `base + residual`
identity. A one-step real-model smoke used 25 FP32 parameters, completed with
baseline/final both `2.828125` visible tokens/step on 64 anchors, and changed
the intended adapter tensor to a maximum absolute value of `0.001`. The
four-GPU screen compares cosine rates `1e-2`, `3e-3`, `1e-3`, and `3e-4` at
`k=4` for 8,192 steps.

That screen is closed as a no-win. Artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-target-fusion-k4-mixed-4gpu-20260710T122203Z
```

| Candidate | Baseline visible | Final visible | Raw delta | Scenario delta | Scenario 95% CI | Stability | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| fusion `1e-2` | 2.7832 | 2.8057 | +0.0225 | +0.0230 | `[-0.0010, 0.0469]` | pass | too small |
| fusion `3e-3` | 2.7754 | 2.7891 | +0.0137 | +0.0157 | `[-0.0077, 0.0402]` | fail | no win |
| fusion `1e-3` | 2.7842 | 2.7861 | +0.0020 | +0.0021 | `[-0.0116, 0.0148]` | fail | no win |
| fusion `3e-4` | 2.7822 | 2.7813 | -0.0010 | +0.0001 | `[-0.0167, 0.0173]` | fail | no win |

The best row changed only 5.8% of anchors and missed both the Holm-adjusted
exploratory test and the `+0.25` useful-effect floor. This lightweight
approximation does not reproduce DFlare's gain; do not continue scalar fusion
rates. Compact analysis is
`diagnostics/qwen27-dflash-target-fusion-k4-paired-20260710.json`.

The remaining bounded DFlare mechanism is separate context/noise K/V. Clone
each draft attention layer's current `k_proj` and `v_proj` into target-only
weights after checkpoint loading, freeze the original noise projections, and
train only the context copies. This is exact at initialization, retains the
same two K and two V GEMM calls already present, and adds about `52.43M` BF16
parameters (`100 MiB`) without adding inference FLOPs or launches. Preserve
K-norm, RoPE, masks, positions, and endpoint mixed-attention behavior. Require
same-process hidden/logit parity before training and the same paired material /
stability gate afterward.

Implemented as the default-off `context-kv` scope. In a same-process real-model
comparison, the original shared-K/V forward and the cloned context-K/V forward
were exactly equal (`torch.equal=true`, max absolute hidden-state difference
`0.0`), and all ten cloned tensors exactly matched their source weights. A
one-step XPU smoke trained `52,428,800` BF16 parameters, saved ten adapter
tensors, and changed all ten with maximum absolute update `0.001953125`.
The first four-GPU screen uses 4,096 steps and cosine rates `3e-3`, `1e-3`,
`3e-4`, and `1e-4`; this is still an offline acceptance diagnostic, not an
endpoint speed or quality result.

The context-K/V screen also closes below the material gate. Artifact root:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
adaptation-context-kv-k4-mixed-4gpu-20260710T123451Z
```

| Candidate | Baseline visible | Final visible | Raw delta | Scenario delta | Scenario 95% CI | Stability | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| context K/V `3e-3` | 2.7822 | 2.1396 | -0.6426 | -0.6441 | `[-0.7529, -0.5444]` | fail | destructive |
| context K/V `1e-3` | 2.7793 | 2.7617 | -0.0176 | -0.0156 | `[-0.0710, 0.0451]` | pass | no win |
| context K/V `3e-4` | 2.7822 | **2.8779** | **+0.0957** | **+0.0966** | **`[0.0641, 0.1289]`** | fail | clear but too small |
| context K/V `1e-4` | 2.7793 | 2.7998 | +0.0205 | +0.0206 | `[0.0013, 0.0390]` | fail | too small |

The `3e-4` row passed the exploratory zero-effect/Holm test, but missed the
`+0.25` useful-effect floor and had `1.07%` repeat disagreement. Its curve
plateaued (`2.8545`, `2.8643`, `2.8633`, `2.8779`) rather than pointing to a
large unfinished gain. Separate context K/V is mechanically valid and may be
useful in a from-scratch DFlare checkpoint, but adapting only these weights on
the current corpus cannot justify endpoint integration. Do not sweep more
context-K/V rates in isolation. Compact analysis is
`diagnostics/qwen27-dflash-context-kv-k4-paired-20260710.json`.

## Training-free DDTree acceptance oracle

The adapter screens revealed a different opportunity: at the first greedy
DFlash rejection, the target token is already in the draft distribution's top
4 about `57.6%` of the time, top 8 about `70.0%`, top 16 about `80.6%`, and top
64 about `93.1%` (median rank `4`). A single argmax trajectory discards those
alternatives. DDTree instead builds a best-first tree from the same independent
per-position marginals and lets the target verify multiple paths. This is
training-free and remains lossless when the target owns verification.

The official DDTree source is cloned at `/home/steve/src/ddtree`, commit
`c96427a185677bf4133ed865dd1626a5041aef9b`. New diagnostic
`scripts/evaluate-qwen27-dflash-ddtree-offline.py` reuses the corrected
endpoint-mixed DFlash forward, runtime INT8 target head, and target-owned trace
labels. It performs one DFlash forward per anchor, reports the vanilla greedy
path and every requested tree budget, and is explicitly not throughput,
quality, or LocalMaxxing evidence. Its heap/tree output matched the official
builder in 60 additional random structural parity cases.

A 16-anchor `k=8` one-pass smoke was promising but is only a smoke:

| Method | Mean visible depth |
| --- | ---: |
| vanilla DFlash greedy | 3.6875 |
| DDTree budget 8 | 4.0000 |
| DDTree budget 16 | 4.3125 |
| DDTree budget 32 | **4.8750** |

The next diagnostic runs four independent horizons (`k=4/8/12/15`) on four
GPUs with 1,024 heldout anchors each and a budget ladder. Advancement requires
a broad, stable accepted-depth gain whose conservative verifier-node cost can
plausibly beat the current strict endpoint. Actual promotion would still need
branch-aware GDN/DeltaNet state verification, graph-safe cache compaction, and
the full strict fresh endpoint quality/speed gate.

The 4-GPU sweep completed with 1,024 heldout anchors per lane:

| Horizon | Vanilla visible | Small practical tree | Small-tree visible | Largest budget | Largest-budget visible |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 2.7832 | 16 | 3.4268 | 64 | 3.7617 |
| 8 | 3.1143 | 32 | 4.0137 | 128 | 4.4619 |
| 12 | 3.1914 | 24 | 4.0293 | 192 | 4.7236 |
| 15 | 3.2979 | 30 | **4.2031** | 240 | **4.8906** |

The gain was broad rather than one family dominating: the selected practical
point for every horizon improved all `24/24` family-by-task scenarios. Scenario
mean deltas were `+0.31` to `+0.82` for `k4/b16`, `+0.69` to `+1.50` for
`k8/b32`, `+0.56` to `+1.14` for `k12/b24`, and `+0.62` to `+1.47` for
`k15/b30`. A three-pass repeated confirmation is still required because the
first sweep intentionally used one deterministic pass per horizon.

This is a material training-free acceptance result, not a speed result. The
most relevant low-row points are `k=15/budget=15` at `3.9355` visible depth
(16 verifier rows including the root), `k=8/budget=16` at `3.7705` (17 rows),
and `k=8/budget=32` at `4.0137` (33 rows). To reach `100 tok/s`, those shapes
would need total target+draft steps below about `39.36`, `37.71`, and `40.14 ms`
respectively. The current valid MTP3 step is about `40.26 ms` at only four
linear verifier rows, while the corrected eager DFlash `k=8` endpoint was about
`52.5 ms/step`; therefore DDTree is promising enough for a row-cost/GDN design
gate, but it has not yet demonstrated a 100 tok/s cost envelope.

Compact tracked result:
`diagnostics/qwen27-dflash-ddtree-oracle-4gpu-20260710.json`. Full per-anchor
reports remain under:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/
ddtree-oracle-4gpu-20260710T124417Z
```

Next implementation gate: measure exact target-body cost at verifier row shapes
`9,16/17,31/33` with device events, then proceed only if a branch-aware GDN
tree kernel plus draft/tree overhead has a conservative path above the current
record and toward `100 tok/s`. The old July token-tree endpoints are not a cost
control: source audit proved they flattened siblings into an invalid sequential
GDN chain. A valid implementation must consume parent/depth metadata, fork
complete conv/SSM/ReplaySSM state per node, and promote only the target-verified
winning path.

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
