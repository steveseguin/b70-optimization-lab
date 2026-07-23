# W1 N128 NVMe recovery: UMF loader preflight abort

The second local-NVMe recovery root is closed as an infrastructure-only
abort:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T134648Z
```

It ran on clean boot `0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel
`7.0.0-28-generic`, with taint `0`. As in the first local attempt, the gate
verified all 118 local model files, `xpu-smi` version and four-card discovery,
the exact PCI/DRM mapping, and strict four-card idleness.

The corrected `sycl-ls` invocation explicitly removed the invalid ambient
`UR_LOG_LOADER` value, but the inherited dynamic-loader path did not include
the installed oneAPI Unified Memory Framework directory. Both installed Level
Zero adapters consequently reported:

```text
libumf.so.1: cannot open shared object file: No such file or directory
```

`sycl-ls` again exited zero while reporting `Platforms: 0`. The gate required
all four `level_zero` GPU rows and failed closed with status 1. It did not run
the peer binary, either XCCL pass, either N64 gate, N128, a model service, or
model generation. Kernel delta contained only `-- No entries --`; the Xe
reject file was empty and kernel taint remained zero.

The evidence manifest verifies completely. Stable hashes are:

```text
evidence.sha256          9ad9f78af76f1f68000d562d47595d61f2417bd7fd2d38dcce5ffb710edf05b0
final-status.txt         311dd53a575ee5bf200546c299133c1ca3212f93747234a6e6a56d06ecd9bdbc
sycl-ls-verbose.log      43c4721d8bd3dfd6dbc369e098004eda6dedd77acc27a9c87edbe761fc972550
kernel-delta.txt         19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e
kernel-reject-events.txt e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Read-only `ldd` checks show that both pinned adapters resolve every dependency
when invoked with exactly:

```text
/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib
```

The correction pins that loader path and these installed runtime identities:

```text
sycl-ls                           90843629cfe9faaa5b5308524f82399b493b82a64b8db4956284b626d886dfb4
libumf.so.1                       c74cfea0360d09b5072a8227efbc830db36bd57669ca22d190d0fb31fe8e3425
libur_adapter_level_zero.so.0     c0b6d1d3f6f282655a034cfc874f48b2f0196970aea41af372d730bbc2124b48
libur_adapter_level_zero_v2.so.0  bfdf524e1b3ecdd0ee87c3337a768be2b3686e3300765d64dd52d20bd53196b5
```

The new recovery root is registered as:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T135330Z
```

This retry is an infrastructure correction on the same clean boot, not a
performance-conditioned restart. A1 remains the first model generation after
a complete recovery pass.
