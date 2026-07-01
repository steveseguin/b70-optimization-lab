# Qwen3.6 small-N INT8 GEMM candidate rejected

Date: 2026-06-10

## Context

Current accepted runtime:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: vLLM XPU, TP4, 32K, Quark W8A8 INT8, BF16 activations
- Prefix cache: disabled
- XPU graph: PIECEWISE
- Accepted GDN setting: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`

The candidate added an opt-in direct SYCL small-N INT8 GEMM path for the GDN `ba`
projection shape where `N <= 16`. It was gated behind:

```bash
VLLM_XPU_INT8_GEMM_SMALL_N=1
```

## Direct microbench

Artifact:

- `data/qwen36-quark-int8-smalln-gemm-direct-20260610.json`

Direct `_xpu_C.int8_gemm_w8a8` testing on `xpu:0` showed exact BF16 output
matching against the oneDNN path for all tested shapes. The intended `N=16`
shape improved substantially for tiny row counts:

| Shape | Baseline | Candidate | Speedup | Exact |
| --- | ---: | ---: | ---: | --- |
| m=1, k=2048, n=16 | 23.937 us | 9.964 us | 2.40x | yes |
| m=2, k=2048, n=16 | 23.330 us | 9.956 us | 2.34x | yes |
| m=8, k=2048, n=16 | 22.830 us | 9.947 us | 2.30x | yes |
| m=18, k=2048, n=16 | 19.887 us | 10.105 us | 1.97x | yes |
| m=64, k=2048, n=16 | 20.338 us | 19.533 us | 1.04x | yes |

Large `N=2048` cases stayed on the normal oneDNN path and were effectively
unchanged except for one noisy m=8 run.

## Endpoint test

Runtime tmux:

- `qwen36-tp4-smalln-gdnclone-32k`

Candidate launch used the current accepted 32K TP4 env plus:

```bash
VLLM_XPU_INT8_GEMM_SMALL_N=1
```

Endpoint speed artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-smalln-gdnclone-single-r8-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-smalln-gdnclone-single-r8-rerun2-20260610.json`

Results:

| Run | Corrected after-first tok/s | E2E tok/s | Total tok/s | TTFT |
| --- | ---: | ---: | ---: | ---: |
| small-N r8 | 99.3506 | 98.0437 | 196.0875 | 78.758 ms |
| small-N r8 rerun2 | 99.3397 | 98.0911 | 196.1821 | 75.677 ms |

Current accepted controls are higher:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-cclipc-20260610.json`
  - corrected after-first: 99.6577 tok/s
  - e2e: 98.4025 tok/s
  - total: 196.8049 tok/s
- `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`
  - corrected after-first: 99.6301 tok/s
  - e2e: 98.3908 tok/s
  - total: 196.7815 tok/s
- `data/qwen36-quark-int8-tp4-noprefix-restore-after-xpushared-reject-r4-20260610.json`
  - corrected after-first: 99.7816 tok/s
  - e2e: 98.5507 tok/s
  - total: 197.1014 tok/s

## Decision

Rejected at the endpoint speed gate.

The isolated kernel win did not survive the full vLLM graph/runtime path. Because
the candidate was slower than current accepted controls, the full output-quality
suite was not run. The direct kernel check was bit-exact against the existing
path, but the optimization is not useful unless it improves endpoint speed.

## Restore

The candidate `_xpu_C` was removed from the active package and the pre-test
binary was restored:

```text
d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c
```

The accepted endpoint was relaunched as:

- tmux: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend: `127.0.0.1:18080`
- health: OK
- `/v1/models`: OK, `max_model_len=32768`

## Repro artifacts

- Patch: `patches/vllm-xpu-kernels-qwen36-smalln-int8-gemm-rejected-20260610.patch`
- Direct benchmark script: `scripts/bench-qwen36-smalln-int8-gemm.py`
- Direct benchmark data: `data/qwen36-quark-int8-smalln-gemm-direct-20260610.json`
- Endpoint data: `data/qwen36-quark-int8-tp4-noprefix-smalln-gdnclone-single-r8-20260610.json`
- Endpoint rerun data: `data/qwen36-quark-int8-tp4-noprefix-smalln-gdnclone-single-r8-rerun2-20260610.json`
