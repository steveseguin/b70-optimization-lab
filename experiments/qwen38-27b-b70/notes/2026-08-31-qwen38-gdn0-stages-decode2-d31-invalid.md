# Qwen3.8 layer-0 GDN stages call-2 D31 invalid attempt

D31 produced no diagnostic result. Its first model request failed because the
instrumentation called the current seven-argument
`vllm::gdn_attention_core_xpu` operator using an obsolete five-argument
signature. The engine error occurred during prefill before any trace was
written. This is an instrumentation error, not model evidence.

D31r changes only that call signature by passing the layer's production XPU
convolution and SSM state tensors. The causal boundaries and frozen workload
are otherwise unchanged.
