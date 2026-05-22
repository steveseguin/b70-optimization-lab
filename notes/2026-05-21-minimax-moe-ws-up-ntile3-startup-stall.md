# MiniMax M2.7 MoE WS Up N-Tile 3 Startup Stall - 2026-05-21

## Goal

Test whether forcing the llm-scaler MiniMax INT4 MoE workspace up-projection
decode tile to `N_TILE=3` improves single-stream decode throughput on the
current promoted 4x B70 stack. This was a follow-up to the `N_TILE=1` runtime
failure and older larger-tile screens.

This changed only the MoE workspace tile knob:

`VLLM_XPU_MOE_WS_UP_NTILE=3`

No model, quantization, sampling, router precision, speculative decoding,
driver, power, or quality-harness relaxation was used.

## Quality Gate

No quality result was produced. The raw145 n64 exact-output gate never reached
weight loading or generation, so the candidate cannot be treated as
quality-clean.

The log stopped after XCCL worker initialization:

- Last log timestamp: `2026-05-21 07:09:42 -0400`
- Log size: `11,281` bytes
- No quality JSON written
- No `Loading weights` line
- No `Graph capturing` line
- No Python exception in the captured log

After several minutes, one worker process remained at about one full CPU core
while the engine made no log progress. The run was terminated and stale
`/dev/shm/psm_*` handles were cleaned after confirming no live vLLM processes
remained.

## Decision

Reject for now. This candidate failed the first quality-gate prerequisite by
stalling during startup before generation. It was not speed-screened, was not
promoted to the full strict quality suite, and was not submitted to
LocalMaxxing.

This makes `N_TILE=3` unsafe as a runtime knob on the current driver/runtime
stack. If revisited, it should be isolated in a small llm-scaler kernel
microbench or run with extra oneCCL/XCCL diagnostics before using the full
MiniMax model path.

## Artifacts

- Startup-stalled raw145 n64 log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile3-quality-20260521T110917Z/minimax-moe-ws-up-ntile3-raw145-n64.log`
- Graph/cache root used:
  `/mnt/fast-ai/vllm-cache-exp/minimax-moe-ws-up-ntile3-quality-20260521T110917Z`
- Summary data:
  `data/minimax-m27-moe-ws-up-ntile3-startup-stall-20260521.json`
