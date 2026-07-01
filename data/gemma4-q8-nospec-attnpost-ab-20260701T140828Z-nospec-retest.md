# Realistic Suite Paired A/B Analysis

- control run medians: 76.936, 77.191
- candidate run medians: 77.355, 77.884
- paired prompts: 12
- median paired ratio 95% CI: 0.431% / 0.804% / 1.119%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
