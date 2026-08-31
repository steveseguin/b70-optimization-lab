# Qwen3.8 GDN BA + output prefill pad D36 result

D36 passed its complete causal boundary gate. Every recorded stage and the
entire trace JSON were byte-identical across four fresh processes. BA, recurrent
core, normalized output, output row zero, and the full 71-row layer output each
had one hash. Row zero matched the preregistered independent M=512 reference.

The 64-token request still diverged at token index 60 because D36 deliberately
repaired only layer 0 at one call; every other GDN layer/call remained ordinary.
That is not a failure of the localized gate. D37 packages the same treatment
for quantized BA and output projections across all Qwen GDN prefill calls, then
replays this trace and the strict varied-prompt suite.
