# Qwen3.8 Flash-Next FP8 HC gate-mix exact-staged A1 preregistration

Date: 2026-09-01
Status: CPU-qualified and frozen for later one-B70 component execution; no GPU
work, endpoint authorization, or performance claim

## Why this target

A28 measured about `2.94 ms/token` of elementwise work and `4.19 ms/token` of
quantization/cast work. The Qwen4Exp target invokes HC gate mix 97 times per
target token (twice in each of 48 layers plus the final mixer). On XPU, each
call still uses the Torch fallback:

1. BF16 gate to FP32;
2. FP32 sigmoid;
3. BF16 state to FP32;
4. FP32 multiply;
5. FP32 mean;
6. FP32 result to BF16.

The retained whole-Triton replacement is not eligible despite its `77.998%`
isolated speed reduction: randomized production-shape inputs differed by up to
`0.0078125`. This A1 candidate therefore retains Torch sigmoid, multiply, and
mean. It changes only their staging: Torch type promotion converts BF16 state
inside the FP32 multiply, and a fresh BF16 `out` tensor performs the final
conversion inside the FP32 mean. The checkpoint-visible BF16 boundary remains.

This is a new target-side component idea. It is independent of W13-N32 MoE
tuning, immutable norm-affine hoisting, and the closed SiLU/native-HC kernels.
The outside `flashnext-harness` contributes no code to this treatment; its only
transferable speed concept, static whole-decode execution, was already realized
independently in A44.

## Frozen evidence boundary

The experiment-local candidate and its gate are:

- `tools/hc_gate_mix_exact_staged.py`;
- `tools/hc-gate-mix-exact-staged-xpu-graph-gate.py`;
- `tools/test_hc_gate_mix_exact_staged.py`.

CPU validation passes 23 tests. It includes 15 production-shape seed/scale
cells, 100 changing inputs and hashes, input/no-alias checks, contract
rejections, and all 65,280 finite BF16 state encodings through the changed
promotion/reduction-output path. All parity and mutation comparisons use raw
BF16 bytes, so signed zero cannot pass merely through value equality. It is not
XPU evidence.

## Later one-B70 gate

Do not run until the separately frozen root-NVMe link clearance passes and the
ordinary exclusive device/host lifecycle wrapper is added and independently
reviewed. The current experiment-local Python gate is deliberately not a
launch-authorized artifact: the later wrapper must bind its/core hashes, vLLM
authority source/head, Torch build, exact B70 identity, fixed clearance
receipt, exclusive device state, and durable output path. The component gate
then captures 97 production-shape calls in each of a
control and candidate XPU graph. It requires:

- 100/100 changing-input eager outputs byte-identical to the Torch authority;
- 100/100 changing-input graph outputs byte-identical to the same authority;
- 100 distinct graph hashes and unchanged inputs;
- a C-A-A-C timing bracket with at most 2% control drift;
- at least 3% candidate improvement.

A pass authorizes only a default-off vLLM integration patch and a later matched
endpoint arm. A parity miss, unsupported BF16 `out` reduction, graph-capture
failure, or timing miss closes this component without changing any protected
result.
