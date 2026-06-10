# Qwen3.6 Quark INT8 GDN Empty Core Output Rejected

## Candidate

Change the XPU `GatedDeltaNetAttention.forward_xpu()` allocation for `core_attn_out` from unconditional `torch.zeros(...)` to an env-gated `torch.empty(...)` when `VLLM_XPU_GDN_EMPTY_CORE_ATTN_OUT=1`.

The rationale was that the native XPU GDN decode op should write active `core_attn_out`, making the zero-fill unnecessary.

## Runtime

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Snapshot: `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- Candidate cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix-gdn-empty-core`
- Candidate log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix-gdn-empty-core.log`
- Same accepted launch profile plus `VLLM_XPU_GDN_EMPTY_CORE_ATTN_OUT=1`

## Startup Notes

- Model load memory: `8.58 GiB`
- Available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915` tokens
- Max concurrency at 32,768 tokens/request: `62.65x`
- Compile range graph compile: `42.10 s`
- Total `torch.compile`: `56.03 s`
- Engine init profile/cache/warmup: `82.94 s`

Adding the env-gated branch inside the compiled path produced Dynamo warnings trying to inspect `<frozen os>`. It still compiled and served successfully, but startup was slower than the accepted steady-state service path.

## Speed Result

Benchmark shape: 512 prompt tokens, 512 output tokens, 8 repeats, streaming, direct backend URL.

| Run | Artifact | Corrected after-first tok/s | E2E tok/s | Total tok/s | TTFT client |
| --- | --- | ---: | ---: | ---: | ---: |
| current control | `data/qwen36-quark-int8-tp4-noprefix-current-control-single-20260610.json` | `98.5477` | `97.3196` | `194.6392` | `75.71 ms` |
| GDN empty core | `data/qwen36-quark-int8-tp4-noprefix-gdn-empty-core-single-20260610.json` | `97.9799` | `96.7664` | `193.5329` | `75.73 ms` |

Compared with the same-day current control, the candidate regressed by about `0.57` corrected after-first tok/s and about `0.55` e2e tok/s.

## Decision

Rejected. The source hunk was reverted and no full quality suite was run because the speed gate failed.

If this is revisited, avoid a runtime `os.getenv()` branch in the compiled forward path. A static/module-level toggle or direct C++ allocation experiment would be cleaner, but this run gives no evidence that removing the zero-fill improves decode throughput.
