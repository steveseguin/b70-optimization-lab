# Qwen3.8 loaded-model cross-process hash D8c preregistration

Date: 2026-08-31

Status: **preregistered before D8c model loads**

## Question

Standalone INT4 calls are exact at TP1 runtime widths, but vLLM stacks and
packs checkpoint components while loading. Does the fully loaded model contain
different parameter or buffer bytes across fresh processes before inference?

## Frozen diagnostic

- direct-and-ordinary verify the complete pinned model first;
- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU0, TP1, FP16 runtime, MTP0, eager, graph off, four fresh
  containers and distinct cache roots;
- after `GPUModelRunner.load_model` completes, hash every named parameter and
  named buffer including dtype, shape, stride, and complete bytes;
- stop each container after the atomic receipt is written and before any model
  request.

D8c retains D8b's oneCCL device exposure. Its only diagnostic change is to
flatten host tensors before reinterpreting them as bytes, allowing scalar
buffers to be hashed without altering the bytes. The scalar expression is
covered by an inert CPU regression test.

Any missing name, metadata difference, or multiple content hash is a positive
causal finding. Four identical complete receipts are negative evidence only.
No performance, quality, or publication claim follows.
