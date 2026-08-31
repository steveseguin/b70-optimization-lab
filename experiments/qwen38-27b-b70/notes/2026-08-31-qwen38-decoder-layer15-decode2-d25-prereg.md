# Qwen3.8 layer-15 decode-call-2 D25 preregistration

Date: 2026-08-31

Status: **preregistered before D25 model requests**

D24 bounds call-2 divergence to layers 0–31. D25 retains all frozen conditions
and hashes layer 15 after call 2 across four fresh processes. Different output
bounds the source to layers 0–15; exact output bounds it to layers 16–31.
Diagnostic only.
