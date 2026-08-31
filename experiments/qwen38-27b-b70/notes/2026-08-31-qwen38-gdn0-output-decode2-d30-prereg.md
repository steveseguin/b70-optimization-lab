# Qwen3.8 layer-0 GDN-output call-2 D30 preregistration

Date: 2026-08-31

Status: **preregistered before D30 model requests**

D29 identifies layer 0 on decode call 2 as the first divergent layer. D30
retains all frozen conditions and hashes the complete output of layer 0's
`QwenGatedDeltaNetAttention` before post-attention norm and MLP. Different GDN
outputs localize the defect to GDN/state update; exact output localizes it to
the remainder of layer 0. Four fresh processes. Diagnostic only.
