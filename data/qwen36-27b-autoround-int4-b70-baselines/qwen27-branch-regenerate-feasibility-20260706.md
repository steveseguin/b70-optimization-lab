# Qwen27 Branch/Regenerate Feasibility Model

Classification: diagnostic cost model, not a benchmark and not a LocalMaxxing submission.

## Inputs

- draft top-k trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/draft-topk.jsonl`
- verifier trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/verify-trace.jsonl`
- normalized baseline tok/s: `67.51904968102535`
- baseline target-verified tokens/step: `2.6243270614572785`
- inferred baseline step ms: `38.86795021338673`

## Current Acceptance

- aligned steps: `18761`
- accepted-prefix histogram: `{'0': 4498, '1': 4532, '2': 3251, '3': 6480}`
- full-accept rate: `0.3453973668780982`

## Optimistic Legal Envelope

This assumes a future legal branch/regenerate implementation can choose the
target token at the first rejected position when it is inside draft top-k,
then regenerate the remaining suffix perfectly. It is an upper bound, not
an endpoint result.

| cutoff | first-reject in top-k | projected tokens/step | no-extra-cost tok/s |
| ---: | ---: | ---: | ---: |
| 1 | 0.000000 | 2.624327 | 67.519 |
| 2 | 0.373097 | 3.169181 | 81.537 |
| 4 | 0.620064 | 3.517776 | 90.506 |
| 8 | 0.779822 | 3.731304 | 96.000 |
| 16 | 0.874033 | 3.852673 | 99.122 |
| 32 | 0.929322 | 3.920900 | 100.877 |
| 64 | 0.959694 | 3.956506 | 101.794 |

## Extra Step-Cost Budget

Positive numbers are the total additional milliseconds a branch/regenerate
implementation could add per verifier step and still hit the target.

| cutoff | 80 tok/s | 90 tok/s | 100 tok/s | 125 tok/s | 150 tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -6.064 | -9.709 | -12.625 | -17.873 | -21.372 |
| 2 | 0.747 | -3.655 | -7.176 | -13.515 | -17.740 |
| 4 | 5.104 | 0.218 | -3.690 | -10.726 | -15.416 |
| 8 | 7.773 | 2.591 | -1.555 | -9.018 | -13.993 |
| 16 | 9.290 | 3.940 | -0.341 | -8.047 | -13.183 |
| 32 | 10.143 | 4.698 | 0.341 | -7.501 | -12.729 |
| 64 | 10.588 | 5.093 | 0.697 | -7.216 | -12.491 |

## Interpretation

- The current sequential MTP3 trace has useful acceptance but not enough for 100 tok/s at the current step cost; 100 tok/s requires about 3.887 target-verified tokens/step.
- A one-token first-reject correction by itself does not increase output tokens per verifier step; a real win requires regenerating the suffix or an equivalent legal branch/tree drafter.
- The rank-64 perfect-suffix envelope reaches 3.957 tokens/step, which would project to 101.8 tok/s if it added no step cost.
- For a 100 tok/s endpoint at rank-64, the branch/regenerate path can spend at most 0.697 ms extra per verifier step. The budgets for 125/150 tok/s are much tighter and likely require reducing verifier/LM-head cost too.
- This uses the existing BF16-scale top-k64 trace as the acceptance-shape evidence and normalizes step cost to the current valid 67.519 tok/s record. A source prototype still needs strict fresh validation.
