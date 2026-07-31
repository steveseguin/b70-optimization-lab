# Laguna exact decode mainloop specialization component result

Date: 2026-07-31 America/Toronto

Status: **bitwise pass, performance stop; no endpoint authorized or run**.

## Result

The compile-time group-32/vectorized/non-MAD/non-folded width-12 decode
specialization passed raw-BF16 equality against the confirmed GRF128 control
for all three changing inputs on both production shapes (`6/6`). Its isolated
timing did not clear the preregistered material-improvement gate:

| shape | GRF128 control | specialized | speedup |
| --- | ---: | ---: | ---: |
| W13 (`M=120,N=2048,K=3072`) | 0.362201 ms | 0.359867 ms | 1.006484x |
| W2 (`M=120,N=3072,K=1024`) | 0.177335 ms | 0.180068 ms | 0.984819x |

The target executes one W13 and one W2 grouped GEMM per layer. The summed
component medians are therefore `0.5395353 ms` for control and `0.5399356 ms`
for treatment, a projected `0.0742%` regression before endpoint noise. Per the
frozen stop rule, no model service, score-bearing suite, or LocalMaxxing
payload followed.

## Identity and evidence

- source: `ec507e8b0b1bb7ca36adb81565e29c781fbc0cc2`;
- ABI-correct production DSO SHA-256:
  `888d0fd33bf1b355e534b3eda7ea6be2a1d924fc7686f9bdfd2ad0cec6edabf5`;
- DSO ABI: oneAPI 2025.3, `NEEDED libsycl.so.8`;
- component artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-specialized-component-ec507e8-20260731T1047Z`;
- preserved build:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-specialized-build-runtime2025-ec507e8-20260731T1046Z`;
- gate:
  `tools/gate_laguna_decode_exact_specialized.py`;
- runtime lock:
  `tools/runtime-lock-exact-specialized.json`.

## Build-identity incident

The first full configure selected oneAPI 2026 through `FindSYCLToolkit` even
though `CMAKE_CXX_COMPILER` named the 2025.3 compiler. That DSO required
`libsycl.so.9` and failed import before GPU execution because it mixed with the
frozen runtime's older Unified Runtime loader. It is preserved under
`laguna-exact-specialized-build-ec507e8-20260731T1025Z` with SHA-256
`98eca5957f7a9056e1d9030e1dcabfb110b462f6c2baf38b5ac8414e2a7818b1` and
must not be used.

The valid rebuild explicitly pinned `SYCL_COMPILER`, both include paths,
`SYCL_LIBRARY`, `SYCL_LIBRARY_DIR`, and `OCL_LIBRARY` to oneAPI 2025.3. The
actual Ninja link command and final ELF were inspected before execution. Two
earlier component artifact roots record system-Python and ABI-loader failures;
neither reached a kernel or emitted a score.

## Transfer learning

Removing 5,500 dead instructions from a named GPU kernel does not imply a
runtime win when those variants sit behind uniform branches and the live path
already has the same GRF allocation. Require shape-level timing before an
endpoint. The mixed W13/W2 result also argues for independent shape dispatch:
a transformation that helps the larger W13 projection can still lose on W2
and erase the gain when both execute once per layer.

