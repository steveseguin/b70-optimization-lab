# Qwen3.8 Q8 accepted AOT ISA audit

Status: **accepted kernel understood; closes indiscriminate GRF/register tuning**.

The accepted `libggml-sycl.so` was extracted with `clang-offload-extract` and
the BMG-G31 device image containing the hot Q8 reordered-MMVQ kernels was
identified as image 133. Intel's offline disassembler reports the accepted
pair, triple, and quad kernels as SIMD16, 128-GRF mode, eight EU threads, and
no register spills.

Inspection of the inner reordered-Q8 dot-product body confirms coalesced
payload traffic and native DP4A execution: one weight-vector and one
activation-vector load, two half-scale loads, and four DP4A operations for the
VDR4 body. This is consistent with the measured high occupancy and explains
why the selective 256-GRF experiment lost `2.789%`: it traded away residency
without removing spills or fixing a fragmented payload.

The local extraction is retained at
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-aot-disasm`.
Do not globally force 256 GRFs or retry generic load coalescing on this
accepted kernel. A shape- or concurrency-specific VDR experiment remains a
different hypothesis and must still pass exact-token gates.
