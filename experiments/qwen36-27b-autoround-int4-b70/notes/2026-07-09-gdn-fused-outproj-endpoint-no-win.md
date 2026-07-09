# Qwen27 fused GDN output projection endpoint no-win

Date: 2026-07-09

## Classification

Closed endpoint no-win. The native prototype remains useful implementation
evidence, but it must not be promoted or submitted.

## Candidate

The default-off integration replaced the compiled Qwen GDN boundary:

`per-head gated RMSNorm -> flatten -> INC W4A16 out_proj`

with:

`_xpu_C.qwen_gdn_out_proj_int4_w4a16`.

Guards restricted the path to XPU TP1, INC symmetric INT4/group-128,
head-dim 128, SiLU/swISH, norm-before-gate, bias-free, contiguous tensors, and
trace-disabled execution.

Artifacts:

- native prototype:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-gdn-fused-outproj-prototype-20260707.patch`;
- fake registration:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-fused-outproj-fake-reg-20260707.patch`;
- endpoint integration:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-fused-outproj-integration-no-win-20260709.patch`.

## Mechanical validation

- Python syntax and `git diff --check`: pass.
- Temporary oneAPI 2025.3/SYCL8 extension import: pass.
- `torch.compile(fullgraph=True)` custom-op smoke: pass, compiled output
  exactly matched eager custom-op output.
- Generated vLLM computation graph contained the new op in all 48 GDN layers.
  The endpoint branch was therefore active; this was not an env/guard miss.

## Strict fresh diagnostic results

All completed rows used the fixed 12-prompt realistic suite, each prompt once,
streamed token IDs, and `cached_tokens=0` on every request. Quality was
intentionally skipped because the candidate did not beat speed controls.

| GPU | Variant | Median tok/s | p10 | Mean | TTFT ms |
|---:|---|---:|---:|---:|---:|
| 0 | fused candidate | 65.0655 | 61.1258 | 66.1030 | 481.32 |
| 0 | same-source control | 66.6449 | 61.0596 | 66.3310 | 476.12 |
| 1 | control | 65.4554 | 58.3221 | 65.6051 | 475.14 |
| 1 | fused candidate | 65.4936 | 60.7506 | 65.7896 | 470.47 |

Evidence:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-fused-outproj-smoke-gpu0-20260709-20260709T212049Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-fused-outproj-control-gpu0-20260709-20260709T212321Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-fused-outproj-4gpuA-control-gpu1-20260709-20260709T212536Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-fused-outproj-candidate-gpu1-sequential-20260709-20260709T213555Z.json`.

The attempted four-way startup was stopped after three workers spent more than
nine minutes concurrently repacking runtime LM heads. This is a harness/load
contention limitation, not a model crash; the completed GPU-1 control plus a
sequential GPU-1 candidate provided the second device comparison.

## Interpretation

The earlier `6.66x` rows=4 microbenchmark compared the native op against an
eager PyTorch reference. At endpoint scale, torch.compile already fuses the
pointwise norm/gate boundary around the oneDNN projection. The custom
workgroup-reduction prologue did not remove a multi-millisecond compiled
bottleneck: one device regressed by 2.37%, and the second was flat by 0.06%.

Decision:

- no quality run;
- no LocalMaxxing submission;
- endpoint integration and fake registration removed from active vLLM;
- prototype op removed from active XPU-kernel source;
- live `_xpu_C.abi3.so` restored to SHA256
  `aaf055ad665fd222e8404641026191bbbd1dd9fce86ef273b8423cf2af725235`;
- patches and results retained so the eager-vs-compiled mistake is not
  repeated.

Next work should target accepted depth or a genuinely measured compiled
multi-millisecond bucket. The immediate follow-up is a corrected DFlash
acceptance probe with upstream auxiliary-layer indexing and lookahead fixes.
