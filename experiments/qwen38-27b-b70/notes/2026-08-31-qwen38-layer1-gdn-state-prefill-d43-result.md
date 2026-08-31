# Qwen3.8 layer-1 GDN state after prefill D43 result

D43 localizes the remaining drift to **at or before layer 1 prefill**, but it
does not assign causality to the production GDN core.

Across four fresh processes, the reconstructed layer-1 diagnostic observed:

| stage | distinct SHA-256 values |
| --- | ---: |
| hidden input | 4 |
| projected QKVZ | 4 |
| projected BA | 4 |
| convolution state before | 2 |
| SSM state before | 2 |
| core output before norm | 4 |
| output gate | 4 |
| convolution state after | 2 |
| SSM state after | 4 |

The full outputs still first differed at generated token index 60.

This run's generic classifier says `positive-causal-finding-at-or-before-layer`,
which is only a localization label. The hook reconstructs the selected GDN
forward call and therefore bypasses the packaged BA/output projection padding
inside the production method. Because the input to layer 1 already differs,
D43 cannot show that layer 1 created the first drift and cannot validate or
reject the packaged repair.

D44 moves to layer 0 and wraps the original packaged production forward
unchanged. It hashes the input and recurrent states before the call, then the
returned output and states afterward. That preserves the real projection
padding and provides the first valid production-path state boundary.
