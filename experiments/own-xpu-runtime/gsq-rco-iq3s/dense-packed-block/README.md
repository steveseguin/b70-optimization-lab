# Dense packed block hoisting — source preparation

The additive candidate and focused proof are ready for review; no CPU/native compiler or payload extraction has run for this packet. See APPRAISAL.md, selection.json and kernel-delta.patch. Frozen generic control remains unchanged. Root owns compile, payload, device and operational admission.

The CPU proof uses strict FP flags and the actual Host owner/capture facade, including full outputs on the smallest real selected shape of each format, live input/weight changes, stale-capture and strict admission refusals. Independent block scales, exceptional halves and ordered lane/tree bits compare against the original scalar control; there is no tolerance or NaN waiver. Proposed command after review:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/build_cpu.py --build
```

The helper reserves64MiB above27GB, limits GNU AS4GiB and uses the shared compiler coordinator. It retains failed attempts and rejects automatic replay. Native micro source/build recipe reuses39 unchanged non-entry objects, but requires CPU and authenticated-extraction receipts first. Missing fixed.hpp intentionally blocks compilation until extraction. Actual backend ACK precedes allocations, uploads and kernels; failed acknowledgement uses unchanged positive synchronization/retention cleanup. No public performance claim or promotion is implied.
