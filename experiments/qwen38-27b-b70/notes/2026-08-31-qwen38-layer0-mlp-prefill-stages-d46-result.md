# Qwen3.8 layer-0 MLP prefill stages D46 result

D46 isolates the first prefill drift to the loaded INT4 dense-MLP down
projection at M=71:

| stage | distinct SHA-256 values |
| --- | ---: |
| MLP input | 1 |
| gate/up projection output | 1 |
| SiLU-and-multiply output | 1 |
| down projection output | **4** |

The synchronizing hashes between stages changed the eventual full-response
split from token 60 to token 31, so this diagnostic is not a production repair
or performance run. The causal boundary itself is valid: the loaded down
projection received the same complete activation tensor in every process and
its observed output had four hashes.

Because the current 1e90-based kernel does not publish the oneDNN primitive's
completion event to PyTorch's stream, an immediate consumer (including the CPU
trace copy) can race completion. D47 explicitly synchronizes once after this
down projection. An exact result authorizes the cheaper async completion-event
candidate; continued variation requires dispatcher-ordered M=512 padding.
