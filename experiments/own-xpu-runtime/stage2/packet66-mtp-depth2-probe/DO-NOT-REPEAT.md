# Packet66 boundaries

- Do not run GPU work from CPU preparation; the lane-B coordinator owns it.
- Never edit packet61x, the frozen screen trees, packet64 orchestration or
  other jobs' packet65/packet64-attribution paths.
- Do not submit/drain a probe inside `poll_result`; Engine::wait can still own
  an event there. Queue the probe and flush at a quiescent command boundary.
- Restore the exact old attention extent, not the extent recomputed from the
  restored position: the first pass increments position after admitting it.
- Scratch allocations require transaction lifetime in the owner contract.
- A tiny fixture needs `pipeline_mini=true` to use its declared context.
- The current engine is a one-token pipeline. Standalone M=2 operator support
  does not establish a batched M=2 verifier or measured M=3 cost.
- Route union bytes are an opportunity for a future reuse kernel, not the
  bytes the current serial expert kernels read.
- No a2, second-pass time or output equality on the device is claimed until
  the complete 12-prompt coordinator screen passes. See [closeout](CPU-CLOSEOUT.md).
