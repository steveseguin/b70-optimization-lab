# Qwen3.8 layer-0 production GDN state after prefill D44 preregistration

Date: 2026-08-31

Status: **preregistered before D44 model requests**

D43 found that the layer-1 input already differs, but its reconstructed call
bypassed the packaged projection repair. D44 instead wraps the original
production `forward_xpu` at layer 0, prefill call 2 (M=71), on the verified
runtime-sitecopy image. It does not replace or reconstruct any calculation.

The before hashes deliberately synchronize the input and recurrent states.
Across four fresh processes:

- input, convolution state, and SSM state before the call should be identical;
- if returned output or post-call state differs, the unchanged production
  prefill call creates drift despite the explicit before-boundary dependency;
- if all post-call values are identical, the synchronization itself changes
  ordering and D45 will test the smallest production-safe dependency repair.

No performance or production claim is authorized.
