# Qwen27 Branch/Regenerate Feasibility Model

Classification: diagnostic cost model, not a benchmark and not a LocalMaxxing submission.

## Inputs

- draft top-k trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-current-recipe-strict-topk64-branch-envelope-20260707T092955Z/draft-topk.jsonl`
- verifier trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-current-recipe-strict-topk64-branch-envelope-20260707T092955Z/verify-trace.jsonl`
- normalized baseline tok/s: `87.02911429766677`
- baseline target-verified tokens/step: `2.746954076850984`
- inferred baseline step ms: `31.563622116795795`

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
| 1 | 0.000000 | 2.746954 | 87.029 |
| 2 | 0.407687 | 3.283037 | 104.013 |
| 4 | 0.654861 | 3.603561 | 114.168 |
| 8 | 0.792012 | 3.768510 | 119.394 |
| 16 | 0.895252 | 3.889410 | 123.224 |
| 32 | 0.939714 | 3.939082 | 124.798 |
| 64 | 0.966843 | 3.968135 | 125.719 |

## Extra Step-Cost Budget

Positive numbers are the total additional milliseconds a branch/regenerate
implementation could add per verifier step and still hit the target.

| cutoff | 80 tok/s | 90 tok/s | 100 tok/s | 125 tok/s | 150 tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2.773 | -1.042 | -4.094 | -9.588 | -13.251 |
| 2 | 9.474 | 4.915 | 1.267 | -5.299 | -9.677 |
| 4 | 13.481 | 8.476 | 4.472 | -2.735 | -7.540 |
| 8 | 15.543 | 10.309 | 6.121 | -1.416 | -6.440 |
| 16 | 17.054 | 11.652 | 7.330 | -0.448 | -5.634 |
| 32 | 17.675 | 12.204 | 7.827 | -0.051 | -5.303 |
| 64 | 18.038 | 12.527 | 8.118 | 0.181 | -5.109 |

## Interpretation

- The current sequential MTP3 trace has useful acceptance but not enough for 100 tok/s at the current step cost; 100 tok/s requires about 3.156 target-verified tokens/step.
- A one-token first-reject correction by itself does not increase output tokens per verifier step; a real win requires regenerating the suffix or an equivalent legal branch/tree drafter.
- The rank-64 perfect-suffix envelope reaches 3.968 tokens/step, which would project to 125.7 tok/s if it added no step cost.
- For a 100 tok/s endpoint at rank-64, the branch/regenerate path can spend at most 8.118 ms extra per verifier step. The budgets for 125/150 tok/s are much tighter and likely require reducing verifier/LM-head cost too.
- This uses the supplied draft top-k and verifier traces as the acceptance-shape evidence and normalizes step cost to the supplied 87.029114 tok/s baseline. A source prototype still needs strict fresh validation.
