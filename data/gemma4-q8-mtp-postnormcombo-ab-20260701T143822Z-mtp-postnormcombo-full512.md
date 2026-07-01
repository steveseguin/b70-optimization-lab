# Realistic Suite Paired A/B Analysis

- control run medians: 114.073, 114.239
- candidate run medians: 116.870, 117.166
- paired prompts: 12
- median paired ratio 95% CI: -4.273% / 1.026% / 3.120%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
