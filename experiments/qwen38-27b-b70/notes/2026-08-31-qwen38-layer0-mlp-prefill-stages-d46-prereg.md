# Qwen3.8 layer-0 MLP prefill stages D46 preregistration

Date: 2026-08-31

Status: **preregistered before D46 model requests**

D45 isolated the first prefill drift to the dense layer-0 MLP: the MLP input
was exact while its output differed across fresh processes. D46 splits that
same M=71 call into the loaded quantized gate/up projection, SiLU-and-multiply,
and loaded quantized down projection, hashing after each stage.

Across four fresh processes:

- the MLP input must remain byte-identical;
- if gate/up differs, both MLP projections will be tested with model-scoped
  dispatcher-ordered M=512 input construction because down consumes that
  process-dependent activation;
- if gate/up and activation are exact but down differs, the repair will target
  only down projection;
- any candidate must then replay this boundary and the full cross-process
  output gate before strict varied-prompt quality and cold performance tests.

No performance or production claim is authorized.
