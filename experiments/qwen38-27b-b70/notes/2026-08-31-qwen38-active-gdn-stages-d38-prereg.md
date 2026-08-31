# Qwen3.8 active packaged GDN stage trace D38 preregistration

Date: 2026-08-31

Status: **preregistered before D38 model requests**

D37r proved the packaged production GDN forward still differs for identical
input. D38 reconstructs exactly the active editable source at vLLM head
`ac7509e2b`: ordinary QKVZ, the packaged M=512 BA helper, the five-argument
`gdn_attention_core_xpu(core, z, qkvz, ba, prefix)`, gated norm, and the packaged
M=512 output helper. It traces layer 0 call 2 and returns the reconstructed
output. All other calls use the packaged production forward.

Across four fresh processes, compare each stage independently. The first stage
with more than one hash is the remaining causal boundary. Token identity is
recorded but no quality/performance claim is authorized. Any repair must be
preregistered separately after this result.
