# Qwen3.8 Q8 accepted-stack post-reboot kernel census

Date: 2026-08-16

A host-side launch census was run on the accepted direct-Q8 mode-2 binary
after the reboot. It used a real TP2 p0/n1 decode, not the unsafe SYCL device-
event profiler. Both GPUs remained normal and the only kernel warning was the
already-audited boot-time KMS `dma_buf_vmap` warning.

Across 516 graph computes, the census found:

- zero standalone copy-kernel launches;
- 128 allreduces, 128 fused allreduce-add boundaries, and 128 fused
  add+RMS+multiply boundaries per graph execution;
- eight Q8 quantize launches total, with 1,980 dedup hits;
- per two graph executions, 128 reordered and 128 non-reordered Q8 MMVQs for
  K3072/N5120, two of each for K5120/N124160, and 128 of each for
  K8704/N5120.

This closes the planned generic "remove a materialize/copy/requantize round
trip" arm: there is no residual copy kernel in the accepted decode path, and
activation quantization is already almost entirely fused or deduplicated.
Future work must change the cost of the fused MMVQ/collective critical path or
improve concurrency; merely removing an assumed intermediate cannot help.

Raw local evidence:
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-postreboot-census/accepted-p0-n1-census.log`.
