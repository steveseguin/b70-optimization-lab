# Qwen3.8 decoder layer-15 trace D11 preregistration

Date: 2026-08-31

Status: **preregistered before D11 model requests**

D9 found differing final hidden states and D10 found differing layer-31 output
pairs at the known call-60 branch. D11 uses the same immutable image, verified
local model, TP1 eager MTP0 configuration, `sql-debugging` request, and four
fresh empty caches, changing only the selected decoder boundary to layer 15.

Only layer 15's returned hidden-state/residual pair is completely hashed after
that layer executes on call 60. If it differs, the source is at or before layer
15; if exact while the branch remains, the source is in layers 16–31. This is
diagnostic only and cannot promote performance or quality.
