# Qwen3.6 All-Reduce Graph Clone-Off Neutral Screen

Date: 2026-06-10

## Context

The accepted Qwen3.6 no-prefix runtime sets both custom all-reduce clone guards:

- `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1`
- `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`

The graph-side clone is inserted before the compiled custom-op all-reduce call.
The custom-op input clone remains inside the registered `vllm::all_reduce`
implementation. This screen tested whether removing only the graph-side clone
would improve single-request speed while retaining the custom-op clone safety.

## Candidate

Runtime delta from accepted no-prefix:

- `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=0`
- keep `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`

Runtime:

- Session: `qwen36-tp4-noprefix-nographclone-32k`
- Cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-nographclone-32k-noprefix`
- Log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-customar-nographclone-32k-noprefix.log`

Fresh-cache inspection showed the graph-side clone removal worked in the lowered
cache:

- accepted cache sample: `torch.ops.aten.clone.default` present
- no-graph-clone cache: `0` `torch.ops.aten.clone.default` occurrences

## Single-Request Result

Direct-backend p512/n512 streaming, eight measured repeats:

| metric | accepted no-prefix | graph clone off | delta |
| --- | ---: | ---: | ---: |
| corrected after-first output tok/s | `98.0404` | `98.2168` | `+0.1765` |
| end-to-end output tok/s | `96.7747` | `96.9694` | `+0.1948` |
| mean client TTFT | `77.74 ms` | `77.24 ms` | `-0.50 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-nographclone-graph32k-single-20260610.json`

## Decision

Reject as neutral. The graph-side clone removal is mechanically effective, but
the single-request improvement is only about `0.18%`, which is below a useful
promotion threshold and within normal run-to-run noise for this harness.

I did not spend time on quality or aggregate sweeps. Keep
`VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1` in the accepted runtime until a
clone-path change shows a clearer speed gain.
