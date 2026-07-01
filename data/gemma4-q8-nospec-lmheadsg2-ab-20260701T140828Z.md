# Realistic Suite Paired A/B Analysis

- control run medians: 77.047, 76.605
- candidate run medians: 76.548
- paired prompts: 12
- median paired ratio 95% CI: -0.649% / -0.338% / -0.073%
- decision: no_win

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
