# Qwen3.8 Q8 peer-pair collective experiment

Date: 2026-08-16

Status: **unsafe, device-lost on the first bounded smoke; never enable or
retry on the validated stack**.

## Intent

The accepted TP2 direct-Q8 collective retains one device-0 reduction kernel
and then submits one RMS/MUL/Q8 handoff kernel on each B70. A mode-3 prototype
kept the accepted reduction root and moved both handoffs into one peer-visible
device-0 workgroup. It preserved the scalar expressions, subgroup reduction
tree and Q8 block mapping while attempting to remove one submission and one
cross-queue dependency at each of Qwen3.8's 128 TP boundaries.

This was deliberately narrower than the earlier quality-rejected dual-root
prototype: it did not recompute the collective sum on device 1.

## Safety gate and failure

The candidate was built from the accepted mndodd `4302fb599` Qwen3.8 direct-
Q8 source under the same oneAPI 2026.1.1, BMG-G31 AOT and host-memory-fallback-
off configuration. Compilation was bounded to 6 GiB RAM plus 2 GiB swap.

The first and only workload was a 10 GiB-capped `p0/n1/r1` smoke with equal
TP2, F16 KV and `GGML_SYCL_COMM_DIRECT_Q8=3`. The mode-3 banner printed, then
Level Zero returned `UR_RESULT_ERROR_DEVICE_LOST` while the next reordered
weight operation waited. No throughput result was produced.

Kernel evidence from `0000:03:00.0` recorded, during the failure window:

- 183 `Kernel-submitted job timed out` messages;
- 122 completed GT resets;
- repeated `guc_exec_queue_timedout_job` warnings;
- kernel taint value `512` (`W`, warning) for the remainder of this boot.

The process terminated. `xpu-smi discovery` subsequently reported both B70s
in `normal` state, with no model workload left running. No further GPU
workload was attempted in the warning-tainted boot.

## Root cause and decision

The device-0 kernel wrote device-1 RMS, MUL and Q8 outputs directly. Although
the existing single-kernel reduction can write a narrow peer-visible FP32
vector, extending that pattern across the complete handoff created an invalid
or unsupported dependency/lifetime interaction on this Level Zero/Xe stack.
The failure occurred before any correctness or performance claim was possible.

Do not promote, benchmark, or retry this design. Future collective work must
retain per-device handoff kernels and explicit queue ownership. The exact
incremental source delta is archived only to prevent repetition:

```bash
base64 -d \
  experiments/qwen38-27b-b70/patches/q8-peer-pair-collective-device-lost-unsafe-20260816.diff.gz.b64 \
  | gzip -dc > /tmp/q8-peer-pair-unsafe.diff
```

Decoded patch SHA-256:
`6463c0bedb42f372bbbc8a8d7422a7ee6b59ad49204bd646b0b89d6a809f6605`.
The patch is 8,063 bytes / 155 lines. **It is evidence, not a reproduction
instruction.**

Machine-readable metadata is in
[`2026-08-16-q8-peer-pair-collective-unsafe.json`](../data/2026-08-16-q8-peer-pair-collective-unsafe.json).
