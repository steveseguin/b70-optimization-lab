# Realistic Suite Paired A/B Analysis

- control run medians: 76.728, 76.723
- candidate run medians: 76.682, 77.302
- paired prompts: 12
- median paired ratio 95% CI: 0.005% / 0.357% / 0.727%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
