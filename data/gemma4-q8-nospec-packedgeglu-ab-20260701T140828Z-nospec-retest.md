# Realistic Suite Paired A/B Analysis

- control run medians: 77.110, 77.185
- candidate run medians: 76.318, 76.684
- paired prompts: 12
- median paired ratio 95% CI: -1.046% / -0.858% / -0.570%
- decision: no_win

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
