# MiniMax M2.7 MoE WS Up NTile 6 Negative - 2026-05-21

## Goal

Test whether increasing the llm-scaler MiniMax MoE WS up-projection tile shape improves TP4 single-session decode on 4x Intel Arc Pro B70.

Candidate delta on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```bash
export VLLM_XPU_MOE_WS_UP_NTILE=6
```

The promoted path leaves this unset.

## Quality Gate

The raw145 exact-token canary passed before any speed result was considered:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Degenerate/control/NUL checks: passed
- Determinism checks: passed

During the quality run, one Triton-generated reduction hit an Intel `ocloc` internal compiler error:

```text
IGC: Internal Compiler Error: Floating point exception
```

vLLM recovered and generated the expected raw145 output, so this was not treated as a quality failure. It is still a compiler/runtime warning worth tracking because it appeared only while testing this tile shape.

## Full-Graph Harness Mistake

The first warm speed attempt accidentally used the warm harness default compile config, which allowed full decode graph capture. That failed during startup with the known XPU FlashAttention graph limitation:

```text
The sycl_ext_oneapi_work_group_scratch_memory feature is not yet available for use with the SYCL Graph extension.
```

That run produced no throughput result and should not be compared against the promoted path. The valid speed run below used the promoted PIECEWISE graph configuration:

```json
{"use_inductor_graph_partition": true, "compile_sizes": [1], "cudagraph_mode": "PIECEWISE"}
```

## Throughput Probe

Warm in-process vLLM probe, p512/n1536, one warmup plus four measured repeats:

| Run | Mean output tok/s | Mean total tok/s | Output min/max tok/s | Stdev |
| --- | ---: | ---: | ---: | ---: |
| `VLLM_XPU_MOE_WS_UP_NTILE=6` | `85.356995` | `113.809327` | `85.327628` / `85.385321` | `0.028588` |
| Back-to-back promoted control | `92.452403` | `123.269870` | `92.419024` / `92.485876` | `0.028260` |

The candidate is `7.095407` tok/s slower than the paired control, a `7.67%` decode regression.

## Decision

Reject. This tile shape is quality-safe on the raw canary but materially slower than the promoted path. Do not promote and do not submit to LocalMaxxing.

The follow-up direction remains source-level MoE/kernel work rather than broad tile-size knobs: the working set kernels are already very sensitive to shape, cache, and graph-capture behavior.

## Artifacts

- Quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile6-quality-20260521T115244Z/minimax-moe-ws-up-ntile6-raw145-n64.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile6-quality-20260521T115244Z/minimax-moe-ws-up-ntile6-raw145-n64.log`
- Full-graph failed warm log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile6-warm-20260521T115842Z/minimax-moe-ws-up-ntile6-warm-p512n1536.log`
- PIECEWISE warm JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile6-warm-piecewise-20260521T120319Z/minimax-moe-ws-up-ntile6-warm-piecewise-p512n1536.json`
- PIECEWISE warm log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile6-warm-piecewise-20260521T120319Z/minimax-moe-ws-up-ntile6-warm-piecewise-p512n1536.log`
- Promoted control warm JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-control-warm-piecewise-20260521T121051Z/minimax-promoted-control-warm-piecewise-p512n1536.json`
- Promoted control warm log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-control-warm-piecewise-20260521T121051Z/minimax-promoted-control-warm-piecewise-p512n1536.log`
- Summary data: `data/minimax-m27-moe-ws-up-ntile6-negative-20260521.json`
