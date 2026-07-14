# TP4 collective protocol pivot

Date: **2026-07-14**

## Outcome

The independent fixed-address peer-atomic collective is rejected. A direct
hook into the already initialized oneCCL LL256 ring is exact on 40 changing
BF16 `[4096]` inputs across all four B70 ranks, but is slower than the normal
XCCL entry point when ranks are aligned: `27.874 us` versus `21.666 us` at the
slowest rank. It is infrastructure for fusion, not a speed result.

The next implementation boundary is now precise: preserve oneCCL's raw ring
forwarding and replace all three final result stores with the existing MHC
post transform. Patching only the last receive is incorrect because TP4 writes
the completed result through `loadRecvReduceSendWrtback`,
`recvSendWrtback`, and `recvWrtback` for different chunks.

## Why the custom protocol failed

The first implementation published a local mailbox and had peers poll it
through imported Level Zero mappings. Generic SYCL and ESIMD variants both
hung. This repeats earlier B70 evidence that cross-card visibility of a local
mailbox cannot be made reliable with ordinary stores and remote polling.

The second implementation mirrored the apparent oneCCL small-message pattern:
a shared arrival counter, remote atomic add, bounded polling, lane-1
notification, and uncached atomics. It was tested with a dedicated
`sycl::malloc_device` allocation to rule out the PyTorch caching allocator.
Results remained invalid:

- reconstructing the full opaque IPC handle with the received descriptor
  failed with `UR_RESULT_ERROR_OUT_OF_RESOURCES`;
- zeroing the handle and supplying the descriptor allowed import, but peer
  atomic notifications timed out or exposed garbage payloads;
- both the experimental Level Zero file descriptor and the descriptor embedded
  directly in the handle failed to make notification reliable.

The decisive source audit showed that this comparison was based on the wrong
oneCCL route. The real 8 KiB BF16 reduction is above the 4096-byte low-latency
threshold and selects `RingTransmit` with `Rt64_128_PCIE`. It does not use peer
atomics. Each rank writes only to its next ring peer and carries sequence flags
inside the 128-byte messages. The custom atomic path was therefore discarded
instead of receiving further tuning.

The failed implementation is preserved in XPU-kernel commit `b84ac23` on
`experiment/deepseek-tp4-collective-fusion-20260714`.

## Proven oneCCL control path

oneCCL commit `0277eab` on
`experiment/deepseek-b70-ring-fusion-20260714` exports
`ccl_b70_replay_last_bf16_allreduce`. A normal ProcessGroupXCCL reduction first
initializes and retains the private communicator, stream, peer mappings, ring
buffers, and sequence state. The hook then submits the same fixed BF16 ring
without trying to recreate that private state.

The four-rank probe requires a zero status and bitwise equality with normal
XCCL for changing trigonometric inputs. Forty epochs passed on every rank. A
first unaligned event run produced complementary per-rank timings because a
local event completion does not mean every peer has entered its next
collective. Adding rank alignment made the performance comparison valid:
normal XCCL was about `21.65-21.67 us`; the direct hook was about
`27.85-27.87 us`. No standalone promotion is justified.

Structured evidence is in
[`../data/tp4-collective-protocol-gate-20260714.json`](../data/tp4-collective-protocol-gate-20260714.json).

## Exact fusion boundary

In `RingTransmit::runAllreduce`, the final reduced message must first be
forwarded unchanged so downstream peers receive the same raw BF16 sum. Only
the local store may be transformed. For each valid hidden index `h`, the
result must preserve the existing MHC order:

```text
acc[o] = post[o] * float(reduced_bf16[h])
for i in 0..3:
    acc[o] += comb[i,o] * float(residual[i,h])
residual_out[o,h] = bfloat16(acc[o])
```

The specialized path must cover all three final writeback functions, keep the
generic collective untouched, and require TP4, M=1, H=4096, contiguous BF16
inputs, the ring selector, and the exact 8 KiB unchunked route. The principal
risk is register pressure and ring backpressure from performing four output
accumulators per hidden element. Exact/ULP parity and end-to-end graph timing,
not launch-count reduction, decide whether it survives.

## Full-model ring writeback result

The specialized oneCCL implementation now covers all three final writeback
forms, forwards the raw BF16 reduction before local transformation, and exposes
the graph-safe path through
`torch.ops._xpu_C.tp4_oneccl_allreduce_mhc_post_out`. The final component
commits are vLLM `d7883b27a`, XPU kernels `8e301dc`, and oneCCL `edf0e17`.

The first server attempt proved that library-directory precedence alone is not
enough: the private oneCCL C hook must be globally visible before the XPU helper
library resolves it. Guarded `LD_PRELOAD` fixed that failure. The preload also
increased rank 0's startup footprint enough that the 0.95 memory gate missed by
about 0.18 GiB, so the full-model screen used 0.94. This affects reserved KV
capacity, not the single-sequence decode shape, but any claimed future win must
still use a matching-memory control.

The actual decoder passed mixed PIECEWISE capture and FULL decode capture.
Sequential replay returned `1073 -> 437 -> 1073`; exact copy, Paris, and strict
JSON passed; the strict suite passed all 12 cold rows with cached tokens zero.
This establishes that the fused oneCCL final writeback is numerically correct,
uses changing graph inputs, and survives all 62 real model layers.

It is not a performance win. The strict cold median was `29.5955243 tok/s`, p10
`29.1722911`, versus the trustworthy `30.2390162` frontier, a `-2.13%` loss.
The reason is architectural: the current production path already uses one
kernel for MHC-post plus the following MHC-pre. This experiment performs
MHC-post inside the ring but then launches standalone MHC-pre. It removes one
boundary while reintroducing another and adds MHC arithmetic to the ring's
critical progression.

Do not tune or promote this partial boundary. The next viable version must
produce the following MHC-pre outputs during ring completion and replace the
existing fused post/pre kernel completely. Structured evidence is in
[`../data/tp4-ring-mhc-post-fullmodel-20260714.json`](../data/tp4-ring-mhc-post-fullmodel-20260714.json).
