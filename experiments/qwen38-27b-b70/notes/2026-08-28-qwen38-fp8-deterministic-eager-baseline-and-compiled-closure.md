# Qwen3.8 FP8: deterministic compiled TP2 result

## Promoted result

The official-FP8/W8A16 TP2 target now has a strict compiled single-user result.
Two fresh-server attempts, each with an empty compile cache, used the complete
fixed 12-prompt, six-class suite, the natural 512-token cap, raw streamed token
IDs, and no prompt/KV/response cache reuse. Every row reported
`cached_tokens=0`; both workload gates and both independent canary batteries
passed; all 12 complete token arrays matched.

| attempt | class-balanced decode |
| --- | ---: |
| `workwait-r15-A` | 34.025180 tok/s |
| `workwait-r15-B` | 34.038013 tok/s |
| two-attempt median | **34.031596 tok/s** |

The validated container is
`neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15`, image ID
`sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e`.
It is based on vLLM `ac7509e2b`, XPU kernels `1e90ffa672`, official checkpoint
revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, W8A16 enabled, XPU Graph
disabled, TP2, FP16 activations/KV, MTP0, Inductor enabled, and direct oneCCL
P2P.

The source deltas are archived at
`../patches/vllm-qwen38-xpu-deterministic-gdn-ba-state-20260828.patch` and
`../patches/vllm-qwen38-xpu-compiled-gdn-state-ccl-wait-20260828.patch`. They
pad the small GDN B/A prefill projection into stable 256-row reductions, expose
the recurrent conv/SSM cache mutations to the dispatcher, bind compiler-visible
state buffers to the allocated cache, and change XPU all-reduce to explicit
`async_op=True` plus `Work.wait()`. The latter supplies the missing oneCCL
completion dependency without a whole-device drain.

The earlier eager r5 pair remains a qualified fallback at **18.910242 tok/s**.
The compiled fix is 79.96% faster by the same strict metric.

## Rejected compiled diagnostics

The candidates below were not promoted. Passing performance/canary gates did
not compensate for failed complete-array repeatability:

| candidate | rates (A/B) | exact prompts | disposition |
| --- | ---: | ---: | --- |
| r7, final-layer synchronization | 33.751 / 33.596 | 9/12 | reject |
| r8, synchronization after each GDN | startup deadlock | — | reject |
| r9, GDN captured inside XPU Graph | 35.07 screen | canaries failed | reject |
| r10, compiler-visible bound state buffers | 33.844 / 33.881 | 9/12 | reject |
| r11, XPU Graph off but Inductor retained | 34.669 / 34.690 | 7/12 | reject |
| r12, r11 + `TORCHINDUCTOR_DETERMINISTIC=1` | 34.675 / 34.682 | 5/12 | reject |
| r13, split collectives at FX boundaries | first request failed: empty GDN state | — | reject |
| r14c, whole-device sync after all-reduce | 22.993 / 22.934 | 12/12 | correctness diagnostic only |
| r15, `async_op=True` + `Work.wait()` | 34.025 / 34.038 | 12/12 | **promote** |

The r11 result proved XPU Graph was not the only source. r14c then localized the
remaining problem to incomplete collective ordering, while r15 established the
low-overhead fix. XPU Graph remains disabled because this vLLM version warns
that its XPU Graph support is single-GPU only.

## Evidence

The repository contains the raw
[`r15-A`](../data/qwen38-fp8-deterministic-compiled-workwait-20260828-r15a/performance.json)
and [`r15-B`](../data/qwen38-fp8-deterministic-compiled-workwait-20260828-r15b/performance.json)
token-array captures, their adjacent canary/runtime identities and logs, the
[`A/B comparison`](../data/2026-08-28-qwen38-fp8-deterministic-compiled-work-wait-comparison.json),
and the portable
[`summary`](../data/2026-08-28-qwen38-fp8-deterministic-compiled-work-wait.json).
Rejected candidate directories remain on the lab NVMe as diagnostic evidence;
they are not dependencies of the promoted claim.
