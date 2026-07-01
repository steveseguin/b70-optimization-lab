# Realistic Suite Paired A/B Analysis

- control run medians: 77.001, 76.685
- candidate run medians: 77.372, 77.636
- paired prompts: 12
- median paired ratio 95% CI: 0.653% / 0.864% / 1.070%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
