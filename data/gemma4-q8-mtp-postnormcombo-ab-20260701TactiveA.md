# Realistic Suite Paired A/B Analysis

- control run medians: 116.787, 113.962
- candidate run medians: 117.227, 115.861
- paired prompts: 12
- median paired ratio 95% CI: -2.754% / 0.395% / 3.346%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
