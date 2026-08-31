# Qwen3.8 TP1 stacked INT4 cross-process D7 preregistration

Date: 2026-08-31

Status: **preregistered before D7 operator calls**

## Question

D1 proved only TP2 per-shard component widths exact. Are the substantially
larger TP1 stacked runtime INT4 widths unstable across fresh processes?

## Frozen diagnostic

- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU0, four fresh containers, determinism padding enabled;
- runtime shapes derived from the revision-pinned config, checkpoint tensor
  headers, and vLLM stacking contracts:
  - GDN QKVZ: K=5120, N=16384;
  - GDN output: K=6144, N=5120;
  - full-attention QKV/gate: K=5120, N=14336;
  - full-attention output: K=6144, N=5120;
  - merged MLP gate/up: K=5120, N=34816;
  - MLP down: K=17408, N=5120;
- M=1 and every actual prefill row count: 48, 49, 52, 53, 55, 56, 57,
  59, 65, 71, 75, and 78;
- two identical calls per shape/M within each process, plus full output hashes
  across processes.

The separate FP16 GDN B/A projection is already covered by D2. Any multiple
hash is a positive causal finding. A full pass is scoped negative evidence
only and cannot promote model speed or correctness.
