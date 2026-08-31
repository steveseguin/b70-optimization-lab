# Qwen3.8 decoder layer-1 trace D14 invalid result

D14 is invalid for layer localization. A fresh process first diverged at output
token 31, before the target call 60, so the call-60 token histories were not
identical. Differing layer-1 receipts cannot distinguish state propagation from
a layer-1 defect. No causal or performance claim follows.
