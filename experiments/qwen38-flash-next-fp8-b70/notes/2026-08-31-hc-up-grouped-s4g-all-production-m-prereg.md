# Qwen3.8 Flash-Next HC-up grouped S4g all-production-M preregistration

Date: 2026-08-31

Status: frozen before XPU execution; independent static review passed

S3g proved grouped E=1 byte-exact at M64 for all 97 real HC-up weights. The
target endpoint fixes `max_num_seqs=1` and `max_num_batched_tokens=64`, so its
remaining shape gap is every possible final chunk M between 1 and 64. S4g
closes that gap on the same five real checkpoint sentinels used by S2.

Frozen S4g scope:

- sentinels `00-attn`, `00-mlp`, `24-attn`, `47-mlp`, and `final`;
- every integer M from 1 through 64;
- providers exactly `authority`, then `grouped`;
- 320 cells and 640 fresh-process arms;
- attempt 2, repeat r1 only;
- one selected B70, one streamed 6.25 MiB weight, and at most one steady
  output allocation per process;
- no reboot, server, or full-checkpoint load.

Frozen identities:

- model revision:
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- worker SHA-256:
  `61881cea35d970fc6b43fe7db1ba3256709a09e1d4c8d191e129ac0bfd39db8a`;
- driver SHA-256:
  `bb0a7277f46c0f07b19dd531ca49a48f54d32d16f3587f6f998abd8f4ecd5968`;
- S4g canonical plan SHA-256:
  `b937013662bd1af1d56c8b1d8014e9901d8e7be5656e6cb6b0957ae005ef139f`;
- evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s4g-r1-a2-seed20260831`.

The additive tool change preserves every historical smoke/S1/S2/S3/S3g
canonical plan digest. S4g accepts only the two frozen providers and only the
five sentinels at M1--64. Each grouped arm verifies exact `rows=[M]`, immutable
rows/input/weight bytes, fresh output allocation, full BF16 output bytes,
finite and internally repeatable results, model/runtime/loader identity, and
process/receipt/stream closure.

Frozen interpretation:

- any intrinsic arm, closure, mutation, nonfinite, or repeatability failure is
  terminal;
- any grouped mismatch is retained and classifies the source candidate
  ineligible for a treated build;
- 320/320 exact cells, combined with the all-97 M1/M64 evidence, close the
  production M1--64 component correctness gate;
- a pass authorizes only implementation/testing of the separately frozen
  default-off scheduler-bound source candidate;
- it cannot authorize a runtime build, full-model load, endpoint launch,
  throughput claim, or protected-result change by itself;
- timing is descriptive because provider order is fixed.

Frozen command:

```bash
experiments/qwen38-flash-next-fp8-b70/tools/run-hc-up-mgt1-packed-fallback-gate.py \
  --scope s4g --repeat r1
```

The evidence root was absent at freeze time. Independent static review passed
the exact hashes, plan, provider/shape restrictions, row mutation evidence,
legacy-plan preservation, and no-promotion contract. S4g is launchable as
written.
