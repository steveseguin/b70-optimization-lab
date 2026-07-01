# Realistic Suite Paired A/B Analysis

- control run medians: 119.543, 119.600
- candidate run medians: 119.121, 119.331
- paired prompts: 12
- median paired ratio 95% CI: -1.877% / 1.134% / 3.766%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
