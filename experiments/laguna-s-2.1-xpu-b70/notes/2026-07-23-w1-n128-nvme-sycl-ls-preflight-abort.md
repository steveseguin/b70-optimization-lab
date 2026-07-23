# W1 N128 NVMe recovery: SYCL logger preflight abort

The first local-NVMe recovery root is closed as an infrastructure-only abort:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T131632Z
```

It ran on clean boot `0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel
`7.0.0-28-generic`, with taint `0`. The gate verified all 118 local model
files, `xpu-smi` version and four-card discovery, exact PCI/DRM mapping, and
strict four-card idleness.

The next bounded command invoked oneAPI 2026 `sycl-ls` with
`UR_LOG_LOADER=level_info`. That value uses an obsolete logger syntax. The
tool printed:

```text
Wrong format of the UR_LOG_LOADER environment variable value: 'level_info'
No platforms found
Platforms: 0
```

`sycl-ls` nevertheless exited zero. The gate then required all four
`level_zero` GPU rows, found none, and failed closed with status 1. It did not
run the peer binary, either XCCL pass, either N64 gate, N128, a model service,
or model generation. Kernel delta contained only `-- No entries --`; the Xe
reject file was empty and kernel taint remained zero.

The evidence manifest verifies completely. Stable hashes are:

```text
evidence.sha256     06b27c3e2ac0e254c8294aa679face6329323dad2ce06579281bc2d10c343ca3
final-status.txt    73f83e71c30324b36f15b2fe2afefc97112fa2e66a0a23eb25019d784a5a42df
sycl-ls-verbose.log 26baddc04f0c4f14da045b85b32d38d192e832b4119fc5a15971ea353b47ef0b
kernel-delta.txt    19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e
```

The only authorized correction is to explicitly unset `UR_LOG_LOADER` for
the already verbose `sycl-ls` command and use the fresh local root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T134648Z
```

This retry is not conditioned on performance or candidate output. A1 remains
the first model generation after a complete recovery pass.
