# Realistic Suite Repeatability Analysis

- runs: 3
- run medians: 78.657, 79.100, 79.115
- run-median mean: 78.957 tok/s
- run-median CV: 0.330%
- pairwise abs delta p90: 0.577%

Single-run comparisons inside this same-recipe band are unreliable for deltas smaller than the p90 pairwise absolute run-median delta. Use paired A/B blocks and bootstrap CIs for micro-change decisions.
