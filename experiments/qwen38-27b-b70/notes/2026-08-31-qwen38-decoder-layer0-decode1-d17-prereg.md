# Qwen3.8 layer-0 first-decode D17 preregistration

Date: 2026-08-31

Status: **preregistered before D17 model requests**

D15–D16 found exact prefill state through layer 31. D17 retains all frozen
conditions and hashes GDN layer 0 after it executes on recurrent decode call 1.
The initial generated token is identical across the established runs, so this
call has a common history. A differing pair identifies layer-0 recurrent state
as the earliest observed source; exact output advances the decode boundary.
Diagnostic only.
