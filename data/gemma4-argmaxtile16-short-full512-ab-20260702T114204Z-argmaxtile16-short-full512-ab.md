# Realistic Suite Paired A/B Analysis

- control run medians: 120.804, 119.613, 120.180, 110.988
- candidate run medians: 118.805, 122.496, 117.534, 117.317
- paired prompts: 12
- median paired ratio 95% CI: -2.594% / 0.001% / 4.021%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
