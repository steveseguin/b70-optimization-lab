# Realistic Suite Paired A/B Analysis

- control run medians: 115.515, 114.520
- candidate run medians: 119.019, 120.202
- paired prompts: 12
- median paired ratio 95% CI: -1.186% / 3.057% / 7.067%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
