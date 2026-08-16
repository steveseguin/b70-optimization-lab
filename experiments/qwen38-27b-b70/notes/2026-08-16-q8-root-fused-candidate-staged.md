# Qwen3.8 Q8 root-fused collective candidate

Date: 2026-08-16

Status: **compiled and staged; not executed. A clean reboot is required before
the first one-token safety test.**

## Design boundary

This candidate follows the failure boundary established by the rejected
peer-pair experiment:

- device 0 remains the sole reduction root;
- device 0 writes the same shared FP32 sum to device 1 as the accepted path;
- device 0 produces only its own residual/RMS/MUL/Q8 output;
- device 1 retains its own accepted residual/RMS/MUL/Q8 kernel and queue
  ownership;
- no kernel writes device 1's residual, MUL or Q8 output from device 0.

The only structural change is folding the accepted device-0 reduction and
device-0 handoff into one workgroup. Device 1 waits on that root event exactly
as it waits on the accepted reduction event. This removes one submission per
TP boundary if safe and exact. The tid-strided FP32 operation order, subgroup
RMS tree and Q8 block mapping are retained; a required global workgroup fence
separates device-0's tid-strided producer from the remapped Q8 consumer.

Runtime door: `GGML_SYCL_COMM_DIRECT_Q8=4`. The promoted repro remains mode
`2`; mode `4` is not approved.

## Build state

The candidate compiled successfully with the accepted oneAPI 2026.1.1,
BMG-G31 AOT, Release, F16-on, graph/DNN/host-memory-fallback-off settings.
Compilation ran inside a 6 GiB RAM / 2 GiB swap cap and did not execute a GPU
workload.

Local staged paths:

- source: `/mnt/fast-ai/src/llama.cpp-q38-tp2-peer-q8`
- build: `build-sycl-aot-bmg-g31-peer-q8`
- `llama-bench` SHA-256:
  `18ab44dd1bb21ee70bd50fa8bbe02c4b38a67bf59eb6969b0adcfe92538303f0`

Exact incremental patch:
[`q8-root-fused-collective-untested-20260816.diff.gz.b64`](../patches/q8-root-fused-collective-untested-20260816.diff.gz.b64).
Decoded SHA-256:
`e864bf0dafcd323df330761b9048edc46875b020cf38f707175b3c53e019899c`.

## Required post-reboot gate

Do not run this candidate while `/proc/sys/kernel/tainted` retains the warning
from the mode-3 reset storm. After a clean reboot:

1. confirm both B70s are `normal`, kernel taint is clear, and no new Xe fault
   exists;
2. run only `p0/n1/r1` in mode 4 under a 10 GiB RAM / 2 GiB swap cap;
3. require the mode-4 banner, all expected fusion counters and
   `VERIFY_MISMATCH=0`;
4. run the same candidate binary in mode 2 as a recovery/control smoke;
5. only then run a position-balanced mode-2/mode-4 benchmark bracket;
6. promotion requires 12/12 cache-zero endpoint hashes and semantic canaries.

There is no throughput or quality claim yet. Machine-readable state is in
[`2026-08-16-q8-root-fused-candidate-staged.json`](../data/2026-08-16-q8-root-fused-candidate-staged.json).
