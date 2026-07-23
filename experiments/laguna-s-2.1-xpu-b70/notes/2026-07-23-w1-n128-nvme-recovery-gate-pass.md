# W1 N128 NVMe recovery gate pass

The non-generative local-NVMe recovery gate passed completely on clean boot
`0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel
`7.0.0-28-generic`, with kernel taint `0`:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T140536Z
```

It started at `2026-07-23T14:08:28Z`, completed at
`2026-07-23T14:14:15Z`, and exited zero. The gate passed:

- SHA-256 verification of all 118 local target/draft model files;
- exact PCI/DRM mapping and strict four-card idle checks;
- oneAPI 2026 enumeration of all four B70s;
- exact four-device peer read;
- two independent four-rank XCCL passes, each with four single-device checks,
  four rank initializations, four barriers, and four exact all-reduces;
- the historical N64-only oracle on all four cards, 128 calls per card,
  bitwise exact with no N128 dispatch;
- production N64 fixture liveness on all four cards, 12 calls per card; and
- a 66-second strict idle seal with 41 samples, followed by service, port,
  process, kernel-delta, and reject checks.

No N128 dispatch, model service, prompt, benchmark, or model generation was
part of the gate. The final kernel reject count is zero.

The evidence manifest verifies completely. Stable hashes are:

```text
evidence.sha256          0c582de8520a8f2a35ada2cd997693f8719df6e90b993b43ab524bd1087d56e0
summary.json             2f9266dcbf3f4014e09a5c66dc9b68c2651ee113248ad4eb230e845711cce291
final-status.txt         9b148404a6cff040f53b87076e4bc6c8227c6e23f61f05e2bdfba85b9359689c
kernel-delta.txt         df105046b0b04421c97d9b7c3e421b515cfddcff49c377dff7e58010a8df2dfd
kernel-reject-events.txt e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

All four preceding local recovery roots remain immutable, disclosed
infrastructure-only preflight aborts. None generated a model token or exposed
candidate performance. Their corrections were not performance-conditioned.

The frozen campaign may now begin. A1 N64 control must be the first model
generation after this recovery pass, under campaign:

```text
w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z
```

No diagnostic, warmup, candidate, or unrelated generation is permitted before
A1.
