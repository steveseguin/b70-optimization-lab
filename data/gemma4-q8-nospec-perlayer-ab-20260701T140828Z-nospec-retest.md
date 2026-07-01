# Realistic Suite Paired A/B Analysis

- control run medians: 76.564, 76.708
- candidate run medians: 76.644, 77.194
- paired prompts: 12
- median paired ratio 95% CI: 0.009% / 0.391% / 0.747%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
