# Qwen3.8 decoder layer-3 trace D13 preregistration

Date: 2026-08-31

Status: **preregistered before D13 model requests**

D9–D12 bound the call-60 divergence to layers 0–7. D13 retains every frozen
condition and changes only the selected decoder boundary to layer 3, the first
full-attention layer after GDN layers 0–2.

Only layer 3's returned hidden-state/residual pair is hashed after execution.
A difference bounds the source to layers 0–3; an exact pair bounds it to layers
4–7. Four fresh empty-cache processes are required. Diagnostic only.
