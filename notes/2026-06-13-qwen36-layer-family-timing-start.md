# Qwen3.6 Layer-Family Timing Start

Date: 2026-06-13

## Goal

Start the decisive timing trace for the current Qwen3.6 35B A3B Quark W8A8
INT8 endpoint. The immediate purpose is to stop guessing whether the missing
single-request decode time is mainly MoE work, collectives/topology, or
activation/GDN overhead.

## Scope

Current model:

- HF/local model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Serving path:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- Engine: local vLLM XPU tree at `/home/steve/src/vllm`
- Accepted launcher: `scripts/launch-qwen36-quark-int8-accepted.sh`
- TP: 4
- Context target: 32K

## Instrumentation Added

The live vLLM tree now has opt-in no-sync timing labels for:

- Qwen3Next layer family boundaries: linear-attention layers, full-attention
  layers, final norm, per-layer input/post-attention norm, MLP.
- Full attention: QKV projection, Q/K norm, rotary, attention, output gate,
  output projection.
- GDN: input quant, QKVZ W8A8 GEMM, BA W8A8 GEMM, core op, output norm, output
  projection.
- MoE: internal gate, dispatch, router select/topk, quant method total,
  monolithic/custom-op apply, combine, shared-output reduction, final-output
  reduction.
- TP collectives: all-reduce, all-gather, reduce-scatter, reduce-scatterv,
  padded all-gatherv, including call-site labels, tensor shape, dtype, and byte
  count.

The patch artifact is:

- `patches/vllm-qwen36-layer-family-collective-timing-20260613.patch`

## Timing Method

Use no-sync timing first:

- `VLLM_XPU_DECODE_TIMING=1`
- `VLLM_XPU_DECODE_TIMING_ALLOW=1`
- `VLLM_XPU_DECODE_TIMING_SYNC=0`
- `VLLM_XPU_DECODE_TIMING_SUMMARY=1`
- `VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1`

Reason: synchronized per-op timing previously caused a Level Zero device-lost
failure. Narrow synchronized label timing can be tried later only after the
no-sync trace identifies a small set of suspicious labels.

## Decision Gate

- If MoE dispatch/GEMM dominates: prototype the persistent W8A8 MoE layerlet.
- If collectives dominate: run collective-only replay and then TP/topology or
  bypass work.
- If GDN activation/quant dominates: revive exact SiLU-Q and fused beta/alpha
  style work.

## Status

- Operating protocol added to `notes/llm-optimization-recording-policy.md`.
- Timing hooks compile with `py_compile` in the active vLLM source tree.
- Completed the accepted graph-path no-sync trace and an eager/no-graph
  attribution trace.
- Restored the accepted Qwen lane and passed the existing sentinel provenance
  check.
- Result and decision gate are recorded in
  `notes/2026-06-13-qwen36-decisive-timing-trace.md`.
