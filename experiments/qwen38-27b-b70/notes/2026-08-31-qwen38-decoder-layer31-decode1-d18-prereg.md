# Qwen3.8 layer-31 first-decode D18 preregistration

Date: 2026-08-31

Status: **preregistered before D18 model requests**

D17 found exact GDN layer-0 output on first decode call 1. D18 retains every
frozen condition and hashes layer 31's call-1 output pair across four fresh
processes. A difference bounds the first-decode source to layers 1–31; exact
output advances it beyond layer 31. Diagnostic only.
