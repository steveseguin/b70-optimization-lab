# Qwen3.8 Flash-Next HC-up grouped S3g preregistration

Date: 2026-08-31

Status: frozen before XPU execution; independent static review passed

S2 completed all 120 planned arms but did not satisfy the original
all-provider S3 antecedent. Grouped E=1 was byte-exact in 30/30 cells from M2
through M4096. Packed-view and packed-matmul each failed eight low-M cells and
are excluded prospectively rather than reinterpreted.

Frozen S3g scope:

- all 97 real target HC-up checkpoint weights in production order;
- M64 only;
- providers exactly `authority`, then `grouped`;
- 97 cells and 194 fresh-process arms;
- attempt 2, repeat r1 only;
- one selected B70, one streamed 6.25 MiB weight, and at most one steady
  output allocation per process;
- no reboot, server, or full-checkpoint load.

Frozen identities:

- model revision:
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- worker SHA-256:
  `3bf77bca6bed6397710b92b28c966724380de2d9c0b1518674325840d7cb4dfc`;
- driver SHA-256:
  `8db3ed978dc42b70607fe43825f69b8cf2c1b3460e50399bb996382f3cb41855`;
- S3g plan SHA-256:
  `9e408196d7cca634e12fc3d5e86adb957e3122deae998b06dac5e9f4f982c9d8`;
- evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s3g-r1-a2-seed20260831`.

The additive tooling retains the legacy smoke/S1/S2/S3 plan digests exactly.
The worker rejects packed-view and packed-matmul for S3g before parent, XPU,
or evidence work. The driver derives a two-provider plan and validates provider
sequence, process/stream/arm closure, model/runtime/loader identity, finite and
repeatable output, fresh output allocation, and exact bytes to the contiguous
authority independently for every cell. Existing evidence and historical
source hashes remain immutable.

Frozen interpretation:

- any intrinsic arm, closure, mutation, nonfinite, or repeatability failure is
  terminal;
- grouped mismatches are retained and classify S3g negative;
- 97/97 grouped exactness authorizes only a separately designed default-off
  M>1 grouped source-dispatch treatment and focused tests;
- timing remains descriptive because provider order is fixed;
- S3g cannot authorize a rebuild, full-model load, endpoint launch, throughput
  claim, or change to any protected result.

Frozen command:

```bash
experiments/qwen38-flash-next-fp8-b70/tools/run-hc-up-mgt1-packed-fallback-gate.py \
  --scope s3g --repeat r1
```

The evidence root was absent at freeze time. Independent static review passed
the exact source state, provider restriction, plan, hashes, path isolation,
legacy-plan preservation, and no-promotion rules. S3g is launchable as written.
