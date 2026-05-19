# MiniMax Current-High CCL Fabric Vertex Override Retest

Date: 2026-05-19

## Summary

`CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` was retested against the current strict high after the MiniMax full-forward MoE custom-op and MoE-output-allreduce-inside-custom-op improvements. Earlier tests were on older stacks, so this run checked whether the oneCCL topology override helps once the model path is already faster and more graph-contained.

Candidate recipe:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Baseline recipe: FP16 activations, AutoRound INT4 W4A16, default XPU FlashAttention v2, PIECEWISE XPU graph, exact MiniMax router logits feeding llm-scaler INT4 MoE work-sharing, clone-safe compiled allreduce custom-op, direct in-place Q/K variance scale, MoE output allreduce inside the MoE custom-op, and MiniMax decode-sized router-linear plus fused MoE inside a guarded full-forward custom-op boundary
- Added env: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`
- Shape: p512/n1536, ctx2048, batch 1, MBT512, block256

Result:

- Candidate: `89.037858` output tok/s, `118.717144` total tok/s, mean of four strict benchmark repeats
- Promoted baseline: `89.314195` output tok/s, `119.085594` total tok/s, mean of four strict benchmark repeats
- Delta: `-0.309%` output tok/s and `-0.309%` total tok/s
- Repeats: `89.481882`, `89.570166`, `88.793580`, `88.305805` output tok/s

Decision: reject, keep `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK` unset, and do not submit to LocalMaxxing.

## Quality Gate

The candidate passed:

- raw145 n64 exact: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- 16-repeat arithmetic gate: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Reliability Signal

The arithmetic-repeat quality process passed its hash gate, but the shutdown path printed oneCCL/PMI teardown errors:

- `CCL_ERROR internal_kvs_server.hpp:70 put: read/write error: Broken pipe`
- `pmi_resizable_simple_internal ... failed`
- `terminate called after throwing an instance of 'ccl::v1::exception'`

The strict wrapper continued and the extended sixpack plus all four benchmark repeats completed. Treat this as a reliability negative for the override even though the generated tokens were exact.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-ccl-fabric-vertex-off-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T204456Z-summary.json`
- Quality dir: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-ccl-fabric-vertex-off-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T204456Z-quality`
- Bench JSONs:
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T210030Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T210317Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T210612Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T210900Z.json`

## Learning

For the current four-B70 MiniMax path, forcing oneCCL to bypass fabric vertex connection checking is not a speed path. It is exact-quality but slightly slower and noisier at shutdown. Continue reducing framework/compiler boundaries around collectives rather than overriding oneCCL topology validation.
