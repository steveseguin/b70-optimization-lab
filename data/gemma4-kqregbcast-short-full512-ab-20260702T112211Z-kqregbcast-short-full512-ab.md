# Realistic Suite Paired A/B Analysis

- control run medians: 117.584, 124.161, 115.228, 116.737
- candidate run medians: 116.760, 117.590, 124.444, 115.657
- paired prompts: 12
- median paired ratio 95% CI: -2.666% / -0.040% / 3.119%
- decision: no_win

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
