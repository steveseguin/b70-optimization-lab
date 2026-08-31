# Qwen3.8 decoder layer-1 trace D14 preregistration

Date: 2026-08-31

Status: **preregistered before D14 model requests**

D13 bounded call-60 divergence to layers 0–3. D14 changes only the selected
boundary to GDN layer 1, retaining the immutable TP1 eager MTP0 lane, verified
model, exact request, and four fresh empty caches. A differing output pair
bounds the source to layers 0–1; an exact pair bounds it to layers 2–3.
Diagnostic only.
