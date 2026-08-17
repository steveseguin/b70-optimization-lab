# Qwen3.8 Q8 standalone row SIMD8 body

Date: 2026-08-17

Status: compile-blocked by BMG-G31; do not repeat on this target/compiler

The accepted standalone reordered-Q8 row kernel uses SIMD16. Two lanes split
each 32-value Q8 block, which duplicates the scale load. A default-off
candidate assigned one complete block to each SIMD8 lane, used two aligned
16-byte loads and eight DP4A operations, and packed sixteen independent row
subgroups into a 128-work-item group. Fused pair/triple/quad kernels were not
changed. The idea required a quality gate because it regrouped FP32 sums.

The host C++ object compiled, but the BMG-G31 AOT device link failed through
`ocloc` with exit 245. A separate eight-work-item SYCL probe isolated the
reason without loading the model:

```text
error: in kernel 'typeinfo name for sg8_probe_kernel': Kernel compiled with required subgroup size 8, which is unsupported on this platform
error: backend compiler failed build.
Build failed with error code: -11
icpx: error: gen compiler command failed with exit code 245
```

Compiler: Intel oneAPI DPC++/C++ `2026.1.1.20260724`; AOT target:
`spir64_gen`, device `bmg_g31`. This rules out the exact SIMD8 row-body design
on this BMG target. No llama.cpp GPU workload ran, so there is no performance
or quality claim. Both B70s remained normal and the accepted source and
library were restored byte-for-byte.

- accepted `mmvq.cpp` SHA-256:
  `a4570708075939e3f28bd127a52d4c38f717ecc5d19ba15cfb7ca0d4dffbedf7`;
- accepted library SHA-256:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- diagnostic log:
  `/mnt/fast-ai/artifacts/qwen38-q8-row-sg8-20260817/diagnostics/sg8-probe-build.log`;
- exact candidate increment:
  [`../patches/q8-standalone-row-simd8-compile-blocked-20260817.diff`](../patches/q8-standalone-row-simd8-compile-blocked-20260817.diff).
