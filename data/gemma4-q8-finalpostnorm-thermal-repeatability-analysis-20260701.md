# Realistic Suite Repeatability Analysis

- runs: 4
- run medians: 115.515, 119.019, 114.520, 120.202
- run-median mean: 117.314 tok/s
- run-median CV: 2.324%
- pairwise abs delta p90: 4.409%

Single-run comparisons inside this same-recipe band are unreliable for deltas smaller than the p90 pairwise absolute run-median delta. Use paired A/B blocks and bootstrap CIs for micro-change decisions.
