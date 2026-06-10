# Qwen3.6 INT8 Python Contiguous Removal Rejection

Date: 2026-06-10

## Context

I tested a vLLM source candidate that removes the Python-level
`.contiguous()` before `_xpu_C.per_token_quant_int8_xpu` in the XPU W8A8 INT8
dense linear path.

The current Python wrapper does:

- `x_2d = x.view(-1, x.shape[-1]).contiguous()`
- `_xpu_C.per_token_quant_int8_xpu(x_2d)`
- `_xpu_C.int8_gemm_w8a8(...)`

The XPU C++ quant op already calls `x.contiguous()` internally, so the candidate
left fallback behavior unchanged and skipped only the Python-level contiguous
when the native XPU quant op is active:

- native XPU quant path: pass the view directly
- Python fallback path: keep `x_2d.contiguous()`

This was intended as an exact graph-boundary cleanup with no model-math change.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

## Graph Check

The candidate used a fresh cache root:

- `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix-skip-python-contig`

The generated `computation_graph.py` files no longer contained `view.contiguous`
signatures in the native INT8 linear path, so the intended Python-level graph
change was present.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | accepted refresh | skip Python contiguous |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.6912` | `98.2250` |
| output tok/s end-to-end | `97.4280` | `96.9838` |
| total client tok/s | `194.8560` | `193.9675` |
| mean client TTFT | `77.39 ms` | `76.89 ms` |

Artifacts:

- accepted refresh: `data/qwen36-quark-int8-tp4-noprefix-accepted-single-refresh2-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-skip-python-contig-graph32k-single-20260610.json`
- patch: `patches/vllm-qwen36-skip-python-contiguous-int8-rejected-20260610.patch`

## Decision

Reject the Python-contiguous removal.

The intended graph cleanup occurred, but single-request decode still regressed
by roughly `0.5%`. Keep the accepted dense INT8 wrapper behavior.
