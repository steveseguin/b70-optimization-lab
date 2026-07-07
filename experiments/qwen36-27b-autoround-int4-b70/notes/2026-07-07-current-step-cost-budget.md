# 2026-07-07: Current Qwen27 step-cost budget

## Classification

Diagnostic planning artifact only. This is not a throughput benchmark, not a
quality run, and not a LocalMaxxing submission.

## Why this exists

The current valid Qwen27 row is:

- `webhie/Qwen3.6-27B-int4-AutoRound`;
- target INT8 LM-head with BF16 scales;
- draft INT4 LM-head with BF16 scales;
- ReplaySSM exact GDN state handling, MTP3/cg8, one B70;
- strict fresh median `68.23626314761921 tok/s`;
- current trace accepted depth `2.746954076850984` target-verified
  tokens/verifier step.

That implies an inferred verifier-step cost of
`40.256513914139006 ms/step`.

## Artifact

Reusable script:

```text
scripts/qwen27-step-cost-budget.py
```

Tracked summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-step-cost-budget-20260707.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-step-cost-budget-20260707.md
```

## Current budget

| target tok/s | step ms needed at current depth | step ms to save | tokens/step needed at current step |
|---:|---:|---:|---:|
| 80 | `34.337` | `5.920` | `3.221` |
| 90 | `30.522` | `9.735` | `3.623` |
| 100 | `27.470` | `12.787` | `4.026` |
| 125 | `21.976` | `18.281` | `5.032` |
| 150 | `18.313` | `21.943` | `6.038` |

MTP3 has a hard ceiling of `4` target-verified tokens/step (`3` draft + `1`
bonus). The current rank-64 branch/regenerate optimistic envelope is
`3.9681349578256793` tokens/step, projecting `98.571 tok/s` if it added **zero**
overhead. Therefore current MTP3 branch/regenerate cannot be the primary
`>100 tok/s` route unless verifier-step cost is also reduced.

## Decision

Future Qwen27 work should pass one of these prechecks before endpoint runs:

1. A step-cost patch should plausibly save multiple milliseconds per verifier
   step. Reaching `100 tok/s` at current accepted depth needs `12.787 ms/step`
   saved.
2. A stronger drafter/deeper speculation path should demonstrate accepted depth
   well beyond MTP3. Reaching `125 tok/s` at the current step cost needs about
   `5.03` verified tokens/step; `150 tok/s` needs about `6.04`.
3. MTP3 branch/regenerate remains useful infrastructure only after either step
   cost falls or a deeper verified speculation mechanism exists. Do not spend
   large implementation time on MTP3 branch/regenerate alone as a `>100` path.
