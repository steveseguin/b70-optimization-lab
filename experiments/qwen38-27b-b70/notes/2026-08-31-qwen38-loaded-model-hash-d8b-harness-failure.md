# Qwen3.8 loaded-model hash D8b harness failure

D8b passed direct model verification, initialized oneCCL, and completed model
loading. Before writing a receipt, the diagnostic hook encountered a scalar
FP32 buffer and failed because PyTorch cannot reinterpret a zero-dimensional
float directly as `uint8`. No model request ran. This is **not evidence** for
or against model-state determinism.

D8c changes only the diagnostic byte-view operation from
`cpu().view(torch.uint8)` to `cpu().reshape(-1).view(torch.uint8)`. This retains
the same scalar bytes and also handles all non-scalar tensors. A CPU regression
test covers the scalar case before the retry.
