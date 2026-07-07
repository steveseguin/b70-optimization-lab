# 2026-07-07: EAGLE3 full-vocab five-aux rank-push early stop

## Classification

Diagnostic stronger-drafter training only. This is not an endpoint throughput
result, not a quality run, and not a LocalMaxxing submission.

## Question

After smaller EAGLE/DFlash screens plateaued around `~1.1-1.34` accepted draft
tokens, this screen tested whether a full-vocab Ex0bit draft plus five target
aux layers and a top-k rank-push loss could produce a stronger accepted-prefix
signal on the v6b realistic-context corpus.

The endpoint gate for this Qwen27 recipe is high: current step cost needs
roughly `3+` accepted draft tokens (`4+` visible tokens/step) before endpoint
work is plausible for `>100 tok/s`.

## Setup

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-fullvocab-5aux-rankpush-20260707T114027Z
```

Corpus:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v7-5aux-v6b-4gpu-20260707T095940Z
```

Target:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
```

Draft:

```text
/mnt/fast-ai/llm-cache/hf/manual/Ex0bit--Qwen3.6-27B-PRISM-EAGLE3/full
```

Runner:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle3-fullvocab-5aux-rankpush-screen.sh
```

Tracked compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-fullvocab-5aux-rankpush-earlystop-summary-20260707.json
```

## Early-stop result

The four-GPU screen was stopped at about step `5500-6000` because the heldout
first-token exact rate was far below any plausible endpoint candidate.

Best probe:

```text
variant: fullvocab-5aux-lr3e-6-decay0p25-rank0p2-topk0p5
step: 6000
heldout step-1 exact: 0.3436279296875
heldout loss: 3.0455943439270357
```

The hard current upper bound from step-1 exact is:

```text
5 * 0.3436279296875 = 1.7181396484375 accepted draft tokens
```

That bound assumes every later draft token is correct whenever step 1 is
correct, which is not realistic. It is already well below the `3+` accepted
draft token gate needed for a credible `>100 tok/s` endpoint path.

Other final/near-final probes:

| Variant | Last step | Step-1 exact | Hard upper bound accepted drafts |
| --- | ---: | ---: | ---: |
| `lr1e-6-decay0p25-rank0p2-topk0p5` | `6000` | `0.297852` | `1.489258` |
| `lr1e-6-decay0p5-rank0p1-topk0p25` | `6000` | `0.295654` | `1.478271` |
| `lr3e-6-decay0p25-rank0p2-topk0p5` | `6000` | `0.343628` | `1.718140` |
| `lr3e-6-decay0p5-rank0p1-topk0p25` | `5500` | `0.337646` | `1.688232` |

## Decision

Close this full-vocab five-aux rank-push screen as no-endpoint.

Do not endpoint-wire this draft and do not continue the same training recipe.
The stronger-drafter route now needs a genuinely different mechanism, not more
rank-push continuation on the same full-vocab/five-aux setup. Move effort to
target-body/kernel work or a different drafter architecture with a much higher
step-1 signal before endpoint integration.
