# Qwen3.8 decoder layer-7 trace D12 preregistration

Date: 2026-08-31

Status: **preregistered before D12 model requests**

D9–D11 bound the fresh-process hidden-state divergence to layers 0–15. D12
keeps the immutable image, verified local model, TP1 eager MTP0 lane,
`sql-debugging` request, call 60, seed 42, and four fresh empty caches, changing
only the selected decoder boundary to layer 7.

Only layer 7's returned hidden-state/residual pair is completely hashed after
the layer executes. A difference bounds the source to layers 0–7; an exact pair
bounds it to layers 8–15. This is diagnostic only.
