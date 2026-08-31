# Qwen3.8 layer-1 GDN state at token 60 D42 preregistration

Date: 2026-08-31

Status: **preregistered before D42 model requests**

D41 supplied identical hidden/QKVZ/BA tensors to the layer-1 recurrent core at
call 62 and received four different core outputs. D42 reconstructs the same
site-packages path but hashes `_xpu_conv_state` and `_xpu_ssm_state` to CPU
immediately before the core call, then hashes core/gate and both states after
the call.

The pre-core hash deliberately synchronizes XPU. Interpret the outcomes
strictly:

- different pre-state hashes: divergence accumulated before call 62;
- identical pre-states and identical post/core hashes: missing ordering before
  the core is causal;
- identical pre-states but different post/core hashes: the core itself is
  nondeterministic even after synchronization.

No speed or production repair claim is authorized.
