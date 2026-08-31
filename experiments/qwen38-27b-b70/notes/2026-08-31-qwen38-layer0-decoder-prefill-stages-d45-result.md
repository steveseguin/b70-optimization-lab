# Qwen3.8 layer-0 decoder prefill stages D45 result

D45 identifies the dense layer-0 MLP as the first prefill drift boundary.
Across four fresh processes:

| stage | distinct SHA-256 values |
| --- | ---: |
| decoder hidden input | 1 |
| after input RMS norm | 1 |
| residual after input norm | 1 |
| packaged GDN attention output | 1 |
| after post-attention RMS/add | 1 |
| residual after attention | 1 |
| dense MLP output | **4** |

The full 64-token outputs still first differed at generated token index 60.
Because the MLP received the same complete M=71 input in every process and
returned four different complete outputs, this is a clean production-shaped
causal finding. D46 now splits the MLP into gate/up, activation, and down
projection boundaries before changing production code.
