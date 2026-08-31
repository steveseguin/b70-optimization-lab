# Qwen3.8 decoder layer-31 prefill D16 preregistration

Date: 2026-08-31

Status: **preregistered before D16 model requests**

D15 found exact layer-0 prefill state. D16 retains all frozen conditions and
hashes layer 31's output pair on initial call 0 across four fresh processes.
A difference bounds prefill divergence to layers 1–31; exact output moves the
boundary after layer 31. Diagnostic only.
