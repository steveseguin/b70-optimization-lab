# Qwen3.8 Flash-Next placement overlay on the lossless MTP1 head (`005dc578`)

Exported: 2026-09-06

The exact vLLM overlay of the never-routed-expert placement line: the nine
placement commits (per-expert offset table in the Triton MoE kernel, load-time
placement of cold expert rows in pinned host memory, tuned-map lookups keyed on
the logical expert count) on top of the certified lossless MTP1 head
`1b2a17c1` (itself 55 commits over public `76cfe1cd`, see
`../vllm-lossless-mtp1-1b2a17c1/`). The MTP0 twin of this series is
`q38-placement-clean-v5` at `cb59004b` (the same commits on `2169dbfe`).

- base: `1b2a17c1e7c41985d6a5e0eb324ada4775c25e60` (restore from the lossless-MTP1 bundle first);
- head: `005dc57895896f770157ea94f68e473e7447139e`, tree `d82fb5f2461be1a1f1050c1f681d17f5e7325a17`;
- bundle `vllm-q38-placement-mtp1-005dc578-20260906.bundle` carries tag `q38-placement-mtp1-005dc578`;
- `series.sha256` pins every patch and the bundle; `verify-series.sh --apply` re-creates the tree.

| Patch | Subject |
| --- | --- |
| `0001-XPU-Q38_EXPERT_HOST_PLACEMENT-on-the-promoted-line-p.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT on the promoted line: |
| `0002-XPU-Q38_EXPERT_HOST_PLACEMENT-free-the-original-expe.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: free the original expert |
| `0003-XPU-Q38_EXPERT_HOST_PLACEMENT-rank-serialized-global.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: rank-serialized global |
| `0004-XPU-Q38_EXPERT_HOST_PLACEMENT-v4-per-layer-stage-fre.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT v4: per-layer stage, |
| `0005-XPU-Q38_EXPERT_HOST_PLACEMENT-v5-on-the-promoted-lin.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT v5 on the promoted line: |
| `0006-XPU-Q38_EXPERT_HOST_PLACEMENT-pinned-host-rows-alloc.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: pinned host rows |
| `0007-XPU-Q38_EXPERT_HOST_PLACEMENT-tuned-MoE-config-looku.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: tuned MoE config lookup |
| `0008-XPU-Q38_EXPERT_HOST_PLACEMENT-the-modular-Triton-exp.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: the modular Triton |
| `0009-XPU-Q38_EXPERT_HOST_PLACEMENT-the-M1-phase-config-lo.patch` | [XPU] Q38_EXPERT_HOST_PLACEMENT: the M1 phase-config |
