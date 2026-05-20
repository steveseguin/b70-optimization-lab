# MiniMax Q/K IPC Peer-Polling Recheck

Date: 2026-05-20

## Summary

Rechecked the Level Zero peer-memory path for a possible XPU equivalent of
vLLM's CUDA MiniMax `minimax_allreduce_rms_qk` Lamport kernel.

The hardware setup can import/export peer buffers correctly, but the in-kernel
peer-polling synchronization path is still not viable. XCCL remains much faster
and more reliable for the tiny `[tokens, 2]` Q/K variance allreduce.

## Results

- Peer probe: all 4 B70s visible as Level Zero devices.
- P2P capability: all source-to-destination pairs report `ACCESS`.
- P2P atomics: only self-device pairs report `ACCESS|ATOMICS`; cross-device
  atomics are not advertised.
- Remote fill test: all 16 source-to-destination fills verified.
- Forked IPC test: all 16 source-to-destination IPC opens/fills verified.

Microbenchmarks:

- XCCL tiny allreduce, `[1, 2]` FP32, 4 ranks, synchronized each iteration:
  `0.061791 ms/iter`.
- IPC two-kernel mailbox with CPU `dist.barrier()`, validated: `0.290768 ms/iter`.
- IPC two-kernel mailbox without CPU barrier: failed validation; one rank read
  `[[5.0, 50.0]]` instead of the expected `[[6.5, 65.0]]`.
- IPC single-kernel sequence polling with barrier, validated: `416.863189 ms/iter`.
- IPC single-kernel device-counter polling with barrier, validated:
  `417.954243 ms/iter`.
- IPC single-kernel device-counter polling without validation: `416.477054 ms/iter`.
- IPC atomic-counter polling variant: failed validation.

## Decision

Do not integrate this IPC polling path into vLLM.

The CUDA MiniMax Lamport design depends on peer-visible writes becoming visible
while the polling kernel is running. On this B70/XPU/SYCL stack, normal volatile
loads plus system fences still behave as timeout-limited, and `sycl::atomic_ref`
does not provide a correct cross-device sequence flag. This matches the hardware
reporting: remote access is available, remote atomics are not.

The next source-level work should not be another peer-polling variant unless a
new synchronization primitive is identified. Prefer one of:

- a graph-compatible oneCCL fused primitive,
- a Level Zero event/barrier design that validates without CPU barriers,
- lower-level scheduling around existing XCCL collectives and adjacent kernels,
- or an unrelated MiniMax hot path outside Q/K variance allreduce.

## Artifacts

- Peer probe log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/level-zero-peer-probe-20260520T043359Z.log`
- Single-counter no-validation log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-prototype-bench-20260520T043550Z.log`
- Mode comparison logs:
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-two_kernel_barrier-20260520T043625Z.log`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-single_seq_barrier-20260520T043630Z.log`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-single_counter_barrier-20260520T043638Z.log`
- XCCL tiny allreduce log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/xccL-tiny-allreduce-bench-20260520T043731Z.log`
- Atomic-counter failed validation log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-atomic-counter-20260520T043952Z.log`
- Two-kernel no-barrier failed validation log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-qk-ipc-two-kernel-nobarrier-20260520T044016Z.log`

## Code Changes

- Added `bench_xccl_tiny_allreduce.py` for clean XCCL tiny-shape comparison.
- Added a default-off `MINIMAX_QK_IPC_ATOMIC_COUNTER=1` probe path in the IPC
  prototype. It is documented as failed and should not be used for model runs.
