# Qwen3.8 decoder layer-31 trace D10 result

D10 is a positive boundary result. With identical call-60 MRoPE positions and
the output branch reproduced at token 60, all four fresh processes produced
different complete hashes for both the hidden-state and residual returned by
decoder layer 31. The defect is therefore at or before layer 31.

Only layer 31's post-execution output was synchronized; no preceding layer or
model call was instrumented. This result narrows the next boundary to layer 15
and does not promote performance or quality.
