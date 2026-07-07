# Qwen27 Branch/Regenerate Feasibility Model

Classification: diagnostic cost model, not a benchmark and not a LocalMaxxing submission.

## Inputs

- draft top-k trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-current-recipe-strict-topk64-branch-envelope-20260707T092955Z/draft-topk.jsonl`
- verifier trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-current-recipe-strict-topk64-branch-envelope-20260707T092955Z/verify-trace.jsonl`
- normalized baseline tok/s: `68.23626314761921`
- baseline target-verified tokens/step: `2.746954076850984`
- inferred baseline step ms: `40.256513914139006`

## Current Acceptance

- aligned steps: `2134`
- accepted-prefix histogram: `{'0': 435, '1': 477, '2': 415, '3': 807}`
- full-accept rate: `0.3781630740393627`

## Optimistic Legal Envelope

This assumes a future legal branch/regenerate implementation can choose the
target token at the first rejected position when it is inside draft top-k,
then regenerate the remaining suffix perfectly. It is an upper bound, not
an endpoint result.

| cutoff | first-reject in top-k | projected tokens/step | no-extra-cost tok/s |
| ---: | ---: | ---: | ---: |
| 1 | 0.000000 | 2.746954 | 68.236 |
| 2 | 0.407687 | 3.283037 | 81.553 |
| 4 | 0.654861 | 3.603561 | 89.515 |
| 8 | 0.792012 | 3.768510 | 93.612 |
| 16 | 0.895252 | 3.889410 | 96.616 |
| 32 | 0.939714 | 3.939082 | 97.850 |
| 64 | 0.966843 | 3.968135 | 98.571 |

## Extra Step-Cost Budget

Positive numbers are the total additional milliseconds a branch/regenerate
implementation could add per verifier step and still hit the target.

| cutoff | 80 tok/s | 90 tok/s | 100 tok/s | 125 tok/s | 150 tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -5.920 | -9.735 | -12.787 | -18.281 | -21.943 |
| 2 | 0.781 | -3.778 | -7.426 | -13.992 | -18.370 |
| 4 | 4.788 | -0.217 | -4.221 | -11.428 | -16.233 |
| 8 | 6.850 | 1.616 | -2.571 | -10.108 | -15.133 |
| 16 | 8.361 | 2.959 | -1.362 | -9.141 | -14.327 |
| 32 | 8.982 | 3.511 | -0.866 | -8.744 | -13.996 |
| 64 | 9.345 | 3.834 | -0.575 | -8.511 | -13.802 |

## Interpretation

- The current sequential MTP3 trace has useful acceptance but not enough for 100 tok/s at the current step cost; 100 tok/s requires about 4.026 target-verified tokens/step.
- A one-token first-reject correction by itself does not increase output tokens per verifier step; a real win requires regenerating the suffix or an equivalent legal branch/tree drafter.
- The rank-64 perfect-suffix envelope reaches 3.968 tokens/step, which would project to 98.6 tok/s if it added no step cost.
- For a 100 tok/s endpoint at rank-64, the branch/regenerate path can spend at most -0.575 ms extra per verifier step. The budgets for 125/150 tok/s are much tighter and likely require reducing verifier/LM-head cost too.
- This uses the supplied draft top-k and verifier traces as the acceptance-shape evidence and normalizes step cost to the supplied 68.236263 tok/s baseline. A source prototype still needs strict fresh validation.
