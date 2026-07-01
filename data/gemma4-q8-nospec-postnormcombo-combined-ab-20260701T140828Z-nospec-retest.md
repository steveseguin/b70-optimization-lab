# Realistic Suite Paired A/B Analysis

- control run medians: 77.001, 76.685, 76.486, 77.028
- candidate run medians: 77.372, 77.636, 77.815, 77.537
- paired prompts: 12
- median paired ratio 95% CI: 0.744% / 1.014% / 1.296%
- decision: inconclusive_positive

Promote a micro-change only when the 95% bootstrap lower bound of the paired prompt median ratio is above min_effect_pct and all candidate runs pass the realistic final gate.
