# MiniMax M2.7 Website Quality: Tight Structured Skeleton

## Result

The fast 4x B70 graph path can stay enabled for a simple practical website task when the response is scaffolded and tightly constrained.

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: `vllm 0.20.1-local`, XPU/Level Zero, llm-scaler INT4 MoE, TP4
- Prompt shape: chat prompt plus assistant prefill for the fixed HTML scaffold
- Quality gate: `skeleton_status_html`, strict HTML validation
- Context length: 4096
- Sampling: temperature 0, top-p 1, max tokens 96
- Warmup policy: one validated warmup request excluded from measured metrics

Two independent measured runs:

| Run | Accepted | Rejected | First-pass | Effective measured out tok/s | Post-first out tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| `20260522T085324Z...tight-warm1-repeat30` | 30/30 | 0 | 100% | 94.53 | 94.89 |
| `20260522T085623Z...tight-warm1-repeat30-rerun` | 30/30 | 0 | 100% | 94.46 | 94.82 |

This is materially better than the earlier scaffolded but unconstrained result:

- Earlier scaffolded path: 30/30 accepted after retries, 2 rejects, about 85.46 tok/s cold-inclusive effective and 88.46 tok/s post-first.
- Tight structured path: 30/30 accepted with zero retries in two separate runs, about 94.5 tok/s measured effective.

## What Changed

The harness now has `--warmup-runs`, so startup and first structured-decoder setup are recorded but excluded from the measured service throughput. The output JSON still includes warmup metrics.

The structured suffix regex was tightened. The earlier regex allowed long runs of spaces inside the generated paragraph. One run produced:

```html
<p>All                                                                                        </p><ul
```

That hit `finish_reason=length` and failed validation. The new regex requires normal word chunks separated by single spaces, which preserved the same task while preventing whitespace padding failures.

## Reproduction Command

```bash
source /home/steve/llm-optimizations-publish/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
out=/home/steve/bench-results/minimax-m2.7-website-quality/$(date -u +%Y%m%dT%H%M%SZ)-skeleton-graph-prefill-prefixcache-instruct-structuredregex-tight-warm1-repeat30
mkdir -p "$out"
timeout 35m /home/steve/.venvs/vllm-xpu/bin/python \
  /home/steve/llm-optimizations-publish/scripts/run-minimax-website-task-quality.py \
  --mode graph \
  --prompt-format chat \
  --assistant-prefill skeleton_open \
  --task skeleton_status_html \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --out "$out/result.json" \
  --sites-dir "$out/sites" \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512 \
  --enable-prefix-caching \
  --structured-skeleton-regex
```

## Caveat

This does not prove unconstrained free-form web development quality at 94 tok/s. It proves a useful constrained path: a simple practical HTML task with a fixed scaffold and model-generated paragraph can be served repeatably on the fast graph path without malformed output.

Next work should make the same graph path reliable for richer but still structured site tasks, then progressively loosen the grammar while keeping strict validation.
