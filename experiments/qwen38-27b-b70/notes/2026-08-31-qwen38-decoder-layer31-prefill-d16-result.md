# Qwen3.8 layer-31 prefill D16 result

Layer 31's complete prefill output pair and all four trace receipts were
byte-identical. Initial prefill is deterministic through layer 31. D17 moves to
layer 0 on the first recurrent decode call, whose token history is still common.
