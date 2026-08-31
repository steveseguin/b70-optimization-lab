# Qwen3.8 Flash-Next HC-up M>1 packed-fallback S2 preregistration

Date: 2026-08-31

Status: frozen before XPU execution

S1 passed exact bytes twice for every provider at M2/M64 on real `00-attn`.
S2 widens correctness coverage without changing the worker, runtime, provider
order, evidence contract, or no-promotion rules.

Frozen S2 scope:

- five real checkpoint sentinels: `00-attn`, `00-mlp`, `24-attn`, `47-mlp`,
  and `final`;
- M values `2, 8, 64, 256, 1024, 4096`;
- providers `authority`, `packed_view`, `matmul`, and grouped E=1;
- 30 cells and 120 fresh-process arms;
- attempt 2, repeat r1 only;
- one selected B70, one streamed 6.25 MiB weight, and at most one steady output
  per process.

Frozen identities:

- worker SHA-256:
  `153a51f4a742f461f6bd1a5d4e4e289ca2f91415d11f66e65580d1221d2891c4`;
- driver SHA-256:
  `67dcd9d94fb70aa9c545ea970c175e9a85a6781d445cecebfe442ab8522d1d76`;
- S2 plan SHA-256:
  `7f64407616d85889e98738be7547508fe15ddbda7e5e3a0259464b02d0b0ca4c`;
- evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s2-r1-a2-seed20260831`.

Every provider mismatch is classified per cell while remaining providers
continue. Intrinsic arm failures remain fail-closed. Timings remain
descriptive. Exactness across S2 authorizes only the separately frozen S3
all-97 M64 screen; it does not authorize source integration, endpoint launch,
or a throughput claim.

Frozen command:

```bash
experiments/qwen38-flash-next-fp8-b70/tools/run-hc-up-mgt1-packed-fallback-gate.py \
  --scope s2 --repeat r1
```

S2 performs no reboot, server launch, or full-checkpoint load.
