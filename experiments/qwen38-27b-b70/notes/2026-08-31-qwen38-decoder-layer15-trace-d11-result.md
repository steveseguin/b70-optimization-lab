# Qwen3.8 decoder layer-15 trace D11 result

D11 is a positive boundary result. All four call-60 position hashes matched,
while every layer-15 hidden-state/residual receipt differed. All four runs chose
token `9447`, showing that byte-level state divergence exists even when it does
not cross the greedy argmax boundary. The defect is at or before layer 15.

Only layer 15's post-execution output was synchronized. The next boundary is
layer 7. No performance or quality claim is promoted.
