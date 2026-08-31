# Qwen3.8 decoder layer-31 trace D10 preregistration

Date: 2026-08-31

Status: **preregistered before D10 model requests**

D9 proved that the call-60 final hidden state differs across fresh processes
with identical input IDs and positions. D10 binary-searches the 64-layer decoder
at layer 31 using the same image, local verified model, TP1 eager MTP0 lane,
`sql-debugging` raw-completions request, seed 42, and four fresh empty caches.

Only layer 31's returned hidden-state/residual pair is completely hashed, and
only after layer 31 has executed on model call 60. There is no earlier trace
synchronization. If the pair differs, the source is at or before layer 31; if
it is exact while the output branch remains at token 60, the source is after
layer 31. This diagnostic cannot promote performance or quality.
