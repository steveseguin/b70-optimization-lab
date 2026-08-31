# Qwen3.8 layer-0 decoder prefill stages D45 preregistration

Date: 2026-08-31

Status: **preregistered before D45 model requests**

D39 and the first D44 samples show an identical layer-0 GDN attention output,
while D43 shows the input to layer 1 already differs. D45 brackets the missing
part of the dense layer-0 decoder block at prefill call 2 (M=71): input RMS
normalization, packaged GDN attention, post-attention RMS/add, and MLP.

The selected TP1 call is reconstructed from the same production module methods,
with hashes between stages. This intentionally synchronizes stage boundaries;
it is diagnostic only.

Across four fresh processes:

- input, normalized input, residual, and GDN attention output should be exact;
- the first stage with more than one hash identifies the next repair boundary;
- if the MLP alone differs, D46 will pad only layer-0 prefill MLP projections
  to a stable dispatch shape and leave decode untouched.

No performance or production claim is authorized.
