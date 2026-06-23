# Gemma 4 26B A4B Q8 Sweep Ledger

Use this folder for short summaries of active Gemma 4 B70 sweeps. Large logs
belong under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/`; record the log
path here instead of copying huge files into Git.

## Sweep Entry Template

```markdown
# <label>

Date:
Owner/agent:
GPU / port:

## Hypothesis

Why this should improve valid single-session decode without lowering quality.

## Run Identity

- model repo:
- filename:
- file bytes:
- model revision:
- runtime:
- runtime commit/version:
- backend:
- GPU:
- context:
- batch / ubatch:
- KV cache dtype:
- API mode:
- seed:
- command:
- env delta:
- server log:

## Result

- chat canary:
- output tok/s:
- wall tok/s:
- TTFT:
- prefill tok/s:
- peak VRAM:
- repeat stats:

## Decision

Win / loss / inconclusive / follow-up.

## Artifacts

- benchmark JSON:
- canary JSON:
- payload queue:
- response log:
- patch or diff:
```

## Rules

- Keep one entry per meaningful experiment family.
- Preserve failed runs if they rule out a knob, patch, or runtime path.
- Do not promote a sweep from this folder into `results/` until it passes the
  validity gate documented in
  [`../../../results/gemma4-26b-a4b-q8-b70/validity-gates.md`](../../../results/gemma4-26b-a4b-q8-b70/validity-gates.md).
