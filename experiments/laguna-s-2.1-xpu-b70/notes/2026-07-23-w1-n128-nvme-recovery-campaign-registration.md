# Laguna routed-W1 N128 NVMe recovery campaign registration

Date registered: 2026-07-23 America/Toronto

Status at registration: the host has restarted into a clean compute-only boot.
No XPU probe, model service, model generation, candidate measurement, or
performance observation has occurred on this boot.

## Bound recovery identity

- boot ID:
  `0b7f98a5-e50a-46a5-81ea-15938b55317a`;
- kernel:
  `7.0.0-28-generic`;
- kernel taint:
  `0`;
- default target:
  `multi-user.target`;
- model services:
  `b70-vllm-slot`, `gemma4-26b-q8-quad-backends`, and
  `gemma4-26b-q8-quad-frontdoor` disabled and inactive;
- display manager:
  inactive;
- pre-reboot NVMe tool commit:
  `06a41252fff7a5aadda1cbd223215bb6d91d4778`;
- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`; and
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`.

The recovery root is fixed and fresh:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T131632Z
```

It is on `/dev/nvme0n1p2` (`ext4`). The recovery gate rejects the prior
device-loss boot and the tainted `ntfs3`-incident boot, verifies all 118 local
model files before its first `xpu-smi` call, writes every artifact to ext4,
runs two independent exact XCCL passes, replays the N64-only historical oracle
on all four cards, samples strict idleness for at least 65 seconds, and rejects
any N128 dispatch or model generation.

## Frozen campaign continuation

If and only if the recovery gate passes, the next model generation is A1 in:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z
```

The order remains A1 N64, B1 N128, then B2 N128 and A2 N64 only if the
unchanged phase-one gate passes. The exact, fresh-cold, cache-zero,
one-request-per-prompt, no-rescue, and conservative lower-start record rules
remain those in
[`2026-07-23-w1-n128-nvme-recovery-preregistration.md`](2026-07-23-w1-n128-nvme-recovery-preregistration.md).
The USB copy is backup-only and is not part of any live path.
