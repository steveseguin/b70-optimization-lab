# Q8 final GET_ROWS + output-head Q8 fusion: exact, rejected

Date: 2026-08-17

## Hypothesis

The accepted Qwen3.8-27B Q8 TP2 graph had only eight standalone activation
quantization launches in a bounded `p0/n1` process. A SYCL debug trace proved
that every remaining launch belonged to the final `result_norm ->
output.weight` projection. Each rank executed a `GET_ROWS` for the selected
5,120-element FP32 final row and then launched a reordered-Q8 quantizer.

The guarded `GGML_SYCL_FUSED_GET_ROWS_Q8=1` candidate kept the graph-visible
`result_norm` output, but used one 1,024-thread workgroup to copy the selected
row and populate the output-head Q8 memo after a workgroup barrier. The normal
output-head MMVQ then observed a memo hit. The matcher required the exact
`result_norm`, `result_output`, and `output.weight` roles, one selected row,
F32 input/output, Q8_0 weights, and a 5,120-element contiguous row.

## Mechanism and quality gates

- Accepted library SHA-256: `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`.
- Candidate library SHA-256: `fc4e1a49ec4558e23b7b82d26a692f45b14e3c1ef34776cf4a616e74a2bfc24f`.
- Candidate and control used the same `llama-bench` binary:
  `74e7d48905196285f6e7cd8c8d0b20a8e25cf3f4731b1e2f0f5f6c49ad8d8865`.
- In `p0/n1`, the treatment reported `fused_get_rows=4`; standalone Q8
  launches fell from `8` to `4`, and memo hits rose from `1980` to `1984`.
- A deterministic 64-token endpoint control and treatment produced the exact
  same response SHA-256:
  `4c78c4aae7336f49d3b548edb72a4514b6c10f8df53ce79593ce722d18fe7520`.
- The 64-token treatment removed 134 quantizer launches and retained
  `VERIFY_MISMATCH=0`.

The mechanism was therefore live and output-exact at the smoke gate.

## Performance result

The short `p64/n256/r3` A-B-B-A screen looked promising:

| Arm | Mean decode tok/s |
| --- | ---: |
| A1 control | 36.940448 |
| B1 candidate | 37.596480 |
| B2 candidate | 36.742420 |
| A2 control | 36.683650 |

Pooled candidate throughput was `37.169450` versus `36.812049 tok/s`, or
`+0.971%`. Both position-matched comparisons were positive, so the candidate
advanced to a longer complementary bracket.

The decisive `p64/n512/r3` B-A-A-B bracket reversed the result:

| Arm | Mean decode tok/s |
| --- | ---: |
| C1 candidate | 37.254449 |
| D1 control | 37.653361 |
| D2 control | 37.610350 |
| C2 candidate | 37.044712 |

Both position-matched comparisons rejected the candidate (`-1.059%` and
`-1.504%`). Pooled candidate throughput was `37.149581` versus `37.631856
tok/s`, a `-1.282%` regression. The launch reduction is real, but serializing
the selected-row copy and all 160 Q8 blocks in one workgroup costs more than
the eliminated output-head quantizer submission.

## Decision and restoration

Rejected. Do not repeat this one-workgroup implementation unchanged. A future
retry needs a materially different design, such as retaining multiple gather
workgroups while joining quantization without a cross-workgroup dependency;
simply changing the workgroup size does not solve that synchronization
boundary.

The source was restored byte-for-byte to the accepted snapshot, and the
deployed library was restored to accepted SHA-256 `e75b9603...`. Both B70s
reported `normal`, with no Xe fault, reset, hang, or wedged message during the
experiment.

Raw evidence is retained at:

- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-final-edge-census`;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-final-getrows-q8`;
- `/mnt/fast-ai/artifacts/qwen38-q8-final-getrows-q8-20260817`.
