# Qwen3.8 all dense MLP down M=512 D49 preregistration

Date: 2026-08-31

Status: **preregistered before D49 model requests**

D48 made the complete layer-0 MLP down output exact 4/4 at M=512. D49 applies
that mechanism to every dense `Qwen2MoeMLP` call only when running on XPU with
`32 < M < 512` and no expert gate. It synchronizes before gate/up, after
gate/up, after constructing the padded activation, and after down projection.
This deliberately expensive diagnostic closes every producer/consumer race
while testing the model-wide arithmetic repair. M<=32 decode is unchanged.

Across four fresh processes:

- the first repaired MLP input and output must be exact;
- all 64 generated token IDs and response SHA-256 values must be identical;
- server initialization, request validity, and the trace engagement gate must
  pass without compile fallback or crash.

If the boundary is exact but full output still differs, the next differing
decoder layer is traced. If full output passes, D50 packages the repair and
then replaces host synchronization with measured asynchronous dependencies.
No speed, quality, or production claim is authorized.
